from ctypes import c_float, cast, POINTER

import OpenGL.GL as gl
import numpy as np

import openvr
from openvr.gl_renderer import OpenVrFramebuffer as OpenVRFramebuffer
from openvr.gl_renderer import matrixForOpenVrMatrix as matrixForOpenVRMatrix
from openvr.tracked_devices_actor import TrackedDevicesActor


import gltfutils.gltfutils as gltfu


c_float_p = POINTER(c_float)


class OpenVRRenderer(object):
    def __init__(self, multisample=0, znear=0.1, zfar=1000, poll_tracked_device_frequency=None):
        self.vr_system = openvr.init(openvr.VRApplication_Scene)
        w, h = self.vr_system.getRecommendedRenderTargetSize()
        self.vr_framebuffers = (OpenVRFramebuffer(w, h, multisample=multisample),
                                OpenVRFramebuffer(w, h, multisample=multisample))
        self._multisample = multisample
        self.vr_compositor = openvr.VRCompositor()
        if self.vr_compositor is None:
            raise Exception('unable to create compositor')
        self.vr_framebuffers[0].init_gl()
        self.vr_framebuffers[1].init_gl()
        self._poses = (openvr.TrackedDevicePose_t * openvr.k_unMaxTrackedDeviceCount)()
        self.projection_matrices = (np.asarray(matrixForOpenVRMatrix(self.vr_system.getProjectionMatrix(openvr.Eye_Left,
                                                                                                        znear, zfar))),
                                    np.asarray(matrixForOpenVRMatrix(self.vr_system.getProjectionMatrix(openvr.Eye_Right,
                                                                                                        znear, zfar))))
        self.eye_transforms = (np.asarray(matrixForOpenVRMatrix(self.vr_system.getEyeToHeadTransform(openvr.Eye_Left)).I),
                               np.asarray(matrixForOpenVRMatrix(self.vr_system.getEyeToHeadTransform(openvr.Eye_Right)).I))
        self.view = np.eye(4, dtype=np.float32)
        self.view_matrices  = (np.empty((4,4), dtype=np.float32),
                               np.empty((4,4), dtype=np.float32))
        self.controllers = TrackedDevicesActor(self._poses)
        #self.controllers.show_controllers_only = False
        self.controllers.init_gl()
        self.vr_event = openvr.VREvent_t()
        self._poll_tracked_device_count()
        self._poll_tracked_device_frequency = poll_tracked_device_frequency
        self._frames_rendered = 0
        self._pulse_t0 = 0.0
    def render(self, gltf, nodes, window_size=(800, 600)):
        self.vr_compositor.waitGetPoses(self._poses, openvr.k_unMaxTrackedDeviceCount, None, 0)
        hmd_pose = self._poses[openvr.k_unTrackedDeviceIndex_Hmd]
        if not hmd_pose.bPoseIsValid:
            return
        hmd_34 = np.ctypeslib.as_array(cast(hmd_pose.mDeviceToAbsoluteTracking.m, c_float_p),
                                       shape=(3,4))
        self.view[:3,:] = hmd_34
        view = np.linalg.inv(self.view.T)
        poses = [hmd_34]
        for i in self._controller_indices:
            controller_pose = self._poses[i]
            if controller_pose.bPoseIsValid:
                pose_34 = np.ctypeslib.as_array(cast(controller_pose.mDeviceToAbsoluteTracking.m, c_float_p),
                                                shape=(3,4))
                poses.append(pose_34)
        view.dot(self.eye_transforms[0], out=self.view_matrices[0])
        view.dot(self.eye_transforms[1], out=self.view_matrices[1])
        for eye in (0, 1):
            gl.glViewport(0, 0, self.vr_framebuffers[eye].width, self.vr_framebuffers[eye].height)
            gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, self.vr_framebuffers[eye].fb)
            gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
            gltfu.set_material_state.current_material = None
            gltfu.set_technique_state.current_technique = None
            for node in nodes:
                gltfu.draw_node(node, gltf,
                                projection_matrix=self.projection_matrices[eye],
                                view_matrix=self.view_matrices[eye])
            self.controllers.display_gl(self.view_matrices[eye], self.projection_matrices[eye])
        # self.vr_compositor.submit(openvr.Eye_Left, self.vr_framebuffers[0].texture)
        # self.vr_compositor.submit(openvr.Eye_Right, self.vr_framebuffers[1].texture)
        self.vr_framebuffers[0].submit(openvr.Eye_Left)
        self.vr_framebuffers[1].submit(openvr.Eye_Right)
        # mirror left eye framebuffer to screen:
        # gl.glBlitNamedFramebuffer(self.vr_framebuffers[0].fb, 0,
        #                           0, 0, self.vr_framebuffers[0].width, self.vr_framebuffers[0].height,
        #                           0, 0, window_size[0], window_size[1],
        #                           gl.GL_COLOR_BUFFER_BIT, gl.GL_NEAREST)
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, 0)
        self._frames_rendered += 1
        if self._poll_tracked_device_frequency and self._frames_rendered % self._poll_tracked_device_frequency == 0:
            self._poll_tracked_device_count()
    def process_input(self, button_press_callbacks=None, t_pulse=0.0, strength=0.65*2750):
        for i in self._controller_indices:
            got_state, state = self.vr_system.getControllerState(i, 1)
            if got_state and state.rAxis[1].x > 0.05:
                #if self._t - self._pulse_t0 > t_pulse:
                self.vr_system.triggerHapticPulse(self._controller_indices[0], 0, int(strength * state.rAxis[1].x))
                #self._pulse_t0 = self._t
        if self.vr_system.pollNextEvent(self.vr_event):
            if button_press_callbacks and self.vr_event.eventType == openvr.VREvent_ButtonPress:
                button = self.vr_event.data.controller.button
                if button in button_press_callbacks:
                    button_press_callbacks[button]()
            elif self.vr_event.eventType == openvr.VREvent_ButtonUnpress:
                pass
    def shutdown(self):
        self.controllers.dispose_gl()
        openvr.shutdown()
    def _poll_tracked_device_count(self):
        self._controller_indices = []
        for i in range(openvr.k_unMaxTrackedDeviceCount):
            if self.vr_system.getTrackedDeviceClass(i) == openvr.TrackedDeviceClass_Controller:
                self._controller_indices.append(i)

precision highp float;
attribute vec4 a_Position;
uniform mat4 u_ModelViewMatrix;
uniform mat4 u_ProjectionMatrix;
varying vec3 v_Position;
void main()
{
  vec4 pos = u_ModelViewMatrix * a_Position;
  v_Position = pos.xyz / pos.w;
  gl_Position = u_ProjectionMatrix * pos;
}

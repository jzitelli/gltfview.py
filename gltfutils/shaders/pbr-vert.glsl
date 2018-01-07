precision highp float;
attribute vec3 a_Position;
uniform mat4 u_ModelMatrix;
uniform mat4 u_ProjectionMatrix;
varying vec3 v_Position;
void main()
{
  vec4 pos = u_ModelMatrix * vec4(a_Position.xyz, 1.0);
  v_Position = pos.xyz / pos.w;
  gl_Position = u_ProjectionMatrix * pos;
}
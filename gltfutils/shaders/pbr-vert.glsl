precision highp float;
attribute vec4 a_Position;

#ifdef HAS_NORMALS
attribute vec4 a_Normal;
#endif
#ifdef HAS_TANGENTS
attribute vec4 a_Tangent;
#endif
#ifdef HAS_UV
attribute vec2 a_UV;
#endif

//uniform mat4 u_MVPMatrix;
uniform mat4 u_ProjectionMatrix;
//uniform mat4 u_ModelMatrix;
uniform mat4 u_ModelViewMatrix;

varying vec3 v_Position;
varying vec2 v_UV;

#ifdef HAS_NORMALS
#ifdef HAS_TANGENTS
varying mat3 v_TBN;
#else
varying vec3 v_Normal;
#endif
#endif


void main()
{
  vec4 pos = u_ModelViewMatrix * a_Position;
  v_Position = pos.xyz / pos.w;

  #ifdef HAS_NORMALS
  #ifdef HAS_TANGENTS
  vec3 normalW = normalize(vec3(u_ModelViewMatrix * vec4(a_Normal.xyz, 0.0)));
  vec3 tangentW = normalize(vec3(u_ModelViewMatrix * vec4(a_Tangent.xyz, 0.0)));
  //vec3 normalW = normalize(u_NormalMatrix * a_Normal.xyz);
  //vec3 tangentW = normalize(u_NormalMatrix * a_Tangent.xyz);
  vec3 bitangentW = cross(normalW, tangentW) * a_Tangent.w;
  v_TBN = mat3(tangentW, bitangentW, normalW);
  #else // HAS_TANGENTS != 1
  v_Normal = normalize(vec3(u_ModelViewMatrix * vec4(a_Normal.xyz, 0.0)));
  //v_Normal = normalize(u_NormalMatrix * a_Normal.xyz);
  #endif
  #endif

  #ifdef HAS_UV
  v_UV = a_UV;
  #else
  v_UV = vec2(0.,0.);
  #endif

  // gl_Position = u_MVPMatrix * a_Position; // needs w for proper perspective correction
  gl_Position = u_ProjectionMatrix * (u_ModelViewMatrix * vec4(a_Position.xyz, 1.0));
}

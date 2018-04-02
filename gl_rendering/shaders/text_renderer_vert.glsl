#version 130
const vec2 quadVertices[4] = vec2[4](vec2(-1., -1.),
                                     vec2( 1., -1.),
                                     vec2(-1.,  1.),
                                     vec2( 1.,  1.));

void main(void) {
  gl_Position = vec4(quadVertices[gl_VertexID].xy, 0.02, 1.0);
}

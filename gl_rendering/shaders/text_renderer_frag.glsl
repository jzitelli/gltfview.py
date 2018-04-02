#version 130
uniform sampler2D u_fonttex;
uniform vec4 u_color = vec4(1.0, 1.0, 0.0, 0.0);
uniform vec2 u_screen_size = vec2(800.0, 600.0);
uniform vec2 u_screen_position = vec2(0.0, 0.0);
uniform vec2 u_char_size;
uniform vec2 u_fonttex_size;
uniform vec2 u_texcoords[32];
uniform uint u_nchars;

void main(void) {
  vec2 pixcoords = gl_FragCoord.xy - u_screen_position * u_screen_size;
  vec2 cell = vec2(floor(pixcoords.x / u_char_size.x),
                   ceil(pixcoords.y / u_char_size.y));
  if (cell.y <= 0.0) discard;
  if (cell.y > 1.0) discard;
  if (cell.x < 0.0) discard;
  //if (cell.x >= u_nchars) discard;
  uint col = uint(cell.x);
  if (col >= u_nchars) discard;
  vec2 dtexcoord = vec2((pixcoords.x - u_char_size.x * cell.x) / u_fonttex_size.x,
                        (cell.y * u_char_size.y - pixcoords.y) / u_fonttex_size.y);
  gl_FragColor = vec4(u_color.rgb, texture2D(u_fonttex, u_texcoords[col] + dtexcoord).r);
}

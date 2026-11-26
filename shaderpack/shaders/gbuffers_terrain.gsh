#version 330 compatibility
layout(triangles) in;
layout(triangle_strip, max_vertices = 3) out;
in vec2 vUv[];
in vec4 vTint[];
in vec3 vViewPos[];
in vec3 vNormal[];
flat in int vBlockId[];
flat in int vInset[];
out vec2 uv;
out vec4 tint;
out vec3 viewPos;
out vec3 normal;
flat out int blockId;
flat out int inset;

void corner(int i) {
    uv = vUv[i]; tint = vTint[i]; viewPos = vViewPos[i]; normal = vNormal[i]; blockId = vBlockId[i]; inset = vInset[i];
    gl_Position = gl_in[i].gl_Position;
    EmitVertex();
}

void main() {
    // orientation in clip space, valid even when a corner is behind the camera
    bool away = determinant(mat3(gl_in[0].gl_Position.xyw, gl_in[1].gl_Position.xyw, gl_in[2].gl_Position.xyw)) < 0.0;
    corner(0);
    corner(away ? 2 : 1);
    corner(away ? 1 : 2);
    EndPrimitive();
}

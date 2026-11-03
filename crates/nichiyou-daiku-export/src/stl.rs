//! Binary STL: an 80-byte header, the triangle count, then each triangle's
//! normal and corners as little-endian f32.

use crate::mesh::Mesh;

/// A binary STL header must not start with "solid", which marks ASCII
const HEADER: &[u8] = b"nichiyou-daiku binary STL";

pub fn stl(meshes: &[Mesh]) -> Vec<u8> {
    let count: usize = meshes.iter().map(|m| m.triangles.len()).sum();
    let mut out = Vec::with_capacity(84 + 50 * count);
    let mut header = [0u8; 80];
    header[..HEADER.len()].copy_from_slice(HEADER);
    out.extend_from_slice(&header);
    out.extend_from_slice(&(count as u32).to_le_bytes());
    for mesh in meshes {
        for t in &mesh.triangles {
            let [a, b, c] = t.map(|i| mesh.vertices[i]);
            let n = [
                (b[1] - a[1]) * (c[2] - a[2]) - (b[2] - a[2]) * (c[1] - a[1]),
                (b[2] - a[2]) * (c[0] - a[0]) - (b[0] - a[0]) * (c[2] - a[2]),
                (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]),
            ];
            let length = (n[0] * n[0] + n[1] * n[1] + n[2] * n[2]).sqrt().max(1e-12);
            for v in [n.map(|v| v / length), a, b, c] {
                for value in v {
                    out.extend_from_slice(&(value as f32).to_le_bytes());
                }
            }
            out.extend_from_slice(&0u16.to_le_bytes());
        }
    }
    out
}

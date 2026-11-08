#!/usr/bin/env python3
"""
Starblade Model Dumper
Extracts 3D models from Starblade ROM data (System 21 point ROMs)

Based on:
- MAME source code (namcos21_dsp_c67.cpp, namcos21_3d.cpp)
- Galaxian3 model viewer decompilation
- System 21 Point ROM format documentation
"""

import struct
import os
import sys
from typing import List, Tuple, Dict, Optional
from dataclasses import dataclass


@dataclass
class Vertex:
    """3D vertex with optional color information"""
    x: int
    y: int
    z: int
    
    def __repr__(self):
        return f"V({self.x}, {self.y}, {self.z})"


@dataclass
class Quad:
    """Quad face with vertices and color"""
    color: int
    vertices: Tuple[int, int, int, int]  # Four vertex indices
    
    def __repr__(self):
        return f"Q(color={self.color:04x}, v={self.vertices})"


@dataclass
class PolygonEntry:
    """A complete polygon entry from ROM (contains multiple quads sharing vertices)"""
    quad_index: int
    vertices: List[Vertex]
    quads: List[Quad]
    depth_bias: int
    
    def __repr__(self):
        return f"PolyEntry(quads={len(self.quads)}, verts={len(self.vertices)})"


class StarbladePointROM:
    """Handles Starblade System 21 Point ROM format reading and parsing"""
    
    # ROM file naming patterns
    PATTERN_STARBLADE = {
        0: ("st1-pt0-h.bin", "st1-pt0-u.bin", "st1-pt0-l.bin"),
        1: ("st1-pt1-h.bin", "st1-pt1-u.bin", "st1-pt1-l.bin"),
    }
    
    PATTERN_GALAXIAN3 = {
        0: ("ptoh.bin", "ptou.bin", "ptol.bin"),
    }
    
    # Magic values
    DISPLAY_LIST_TERMINATOR = 0xFFFFFF
    MAX_ADDRESS_TABLE_ENTRIES = 65535
    MAX_POLYGON_ENTRIES = 10000
    MAX_VERTICES_PER_ENTRY = 256
    MAX_QUADS_PER_ENTRY = 256
    
    def __init__(self, rom_dir: str = "roms", bank: int = 0, verbose: bool = False):
        """
        Initialize loader for a specific bank
        
        Args:
            rom_dir: Directory containing ROM files
            bank: Legacy selector; Starblade bank 0 and 1 are loaded together
            verbose: Enable debug output
        """
        self.rom_dir = rom_dir
        self.bank = bank
        self.verbose = verbose
        self.words = []  # All 24-bit words from the ROM bank
        self.address_table = []  # Address table mapping object indices
        self.palette = []  # Loaded palette colors as RGB tuples
        
    def _sign_extend_24bit(self, value: int) -> int:
        """Convert unsigned 24-bit value to signed"""
        if value & 0x800000:
            return value - 0x1000000
        return value

    @staticmethod
    def _unsigned16(value: int) -> int:
        return value & 0xFFFF

    @staticmethod
    def _signed16(value: int) -> int:
        value &= 0xFFFF
        return value - 0x10000 if value & 0x8000 else value
    
    def load_rom_bank(self) -> bool:
        """
        Load both Starblade ROM triplets into MAME's combined point-ROM space
        
        Returns:
            True if successful, False otherwise
        """
        try:
            starblade_banks = []
            for bank_index in (0, 1):
                names = self.PATTERN_STARBLADE[bank_index]
                paths = tuple(os.path.join(self.rom_dir, name) for name in names)
                if not all(os.path.exists(path) for path in paths):
                    starblade_banks = []
                    break
                with open(paths[0], 'rb') as f:
                    high = f.read()
                with open(paths[1], 'rb') as f:
                    upper = f.read()
                with open(paths[2], 'rb') as f:
                    lower = f.read()
                if not (len(high) == len(upper) == len(lower)):
                    print(f"✗ ROM files for bank {bank_index} have different sizes")
                    return False
                starblade_banks.append([
                    self._sign_extend_24bit((high[i] << 16) | (upper[i] << 8) | lower[i])
                    for i in range(len(high))
                ])

            if starblade_banks:
                self.words = starblade_banks[0] + starblade_banks[1]
                if self.verbose:
                    print(f"✓ Loaded Starblade point ROM banks 0 and 1 as one address space ({len(self.words)} words)")
                return True

            if self.bank == 1:
                print("✗ Bank 1 is the continuation of the Starblade point-ROM address space; bank 0 ROMs are required")
                return False

            names = self.PATTERN_GALAXIAN3.get(self.bank)
            if not names:
                print(f"✗ Could not find ROM files for bank {self.bank}")
                return False
            paths = tuple(os.path.join(self.rom_dir, name) for name in names)
            if not all(os.path.exists(path) for path in paths):
                print(f"✗ Could not find ROM files for bank {self.bank}")
                return False
            with open(paths[0], 'rb') as f:
                high = f.read()
            with open(paths[1], 'rb') as f:
                upper = f.read()
            with open(paths[2], 'rb') as f:
                lower = f.read()
            if not (len(high) == len(upper) == len(lower)):
                print(f"✗ ROM files have different sizes: {len(high)}, {len(upper)}, {len(lower)}")
                return False
            self.words = [
                self._sign_extend_24bit((high[i] << 16) | (upper[i] << 8) | lower[i])
                for i in range(len(high))
            ]
            if self.verbose:
                print(f"✓ Loaded {len(self.words)} 24-bit words from Galaxian 3 point ROM")
            return True
        
        except IOError as e:
            print(f"✗ Failed to read ROM files: {e}")
            return False
    
    def load_palette(self, palette_path: str) -> bool:
        """
        Load palette entries stored as Blue, Red, Green, padding.
        
        Args:
            palette_path: Path to palette file
            
        Returns:
            True if successful
        """
        try:
            with open(palette_path, 'rb') as f:
                data = f.read()

            if len(data) % 4:
                print(f"✗ Palette size must be divisible by 4 bytes, got {len(data)}")
                return False
            
            # MAME's xBRG_888 palette entries are four bytes: B, R, G, unused.
            self.palette = []
            for i in range(0, len(data), 4):
                b, r, g = data[i:i + 3]
                self.palette.append((r, g, b))
            
            if self.verbose:
                print(f"✓ Loaded palette with {len(self.palette)} colors from {palette_path}")
                print(f"  (File size: {len(data)} bytes, expected {len(self.palette) * 4} bytes)")
            
            return len(self.palette) > 0
        
        except IOError as e:
            print(f"✗ Failed to load palette: {e}")
            return False
    
    def parse_address_table(self) -> bool:
        """
        Parse the address table at the start of the ROM
        Maps object indices to display list addresses
        
        Returns:
            True if successful
        """
        self.address_table = []
        
        for i in range(min(self.MAX_ADDRESS_TABLE_ENTRIES, len(self.words))):
            addr = self.words[i]
            
            # Sanity check: address should be within ROM bounds
            if addr < 0 or addr >= len(self.words):
                if self.verbose and i < 10:
                    print(f"  Address table entry {i}: 0x{i:04x} -> {addr} (INVALID, stopping)")
                break
            
            self.address_table.append(addr)
        
        if self.verbose:
            print(f"✓ Parsed address table: {len(self.address_table)} object entries")
            if len(self.address_table) > 0:
                print(f"  First few addresses: {self.address_table[:min(5, len(self.address_table))]}")
        
        return len(self.address_table) > 0
    
    def _read_display_list(self, start_addr: int) -> List[int]:
        """
        Parse a display list (sequence of pointers to polygon entries)
        Display list ends with 0xFFFFFF
        
        Args:
            start_addr: Address in ROM where display list starts
            
        Returns:
            List of addresses pointing to polygon entries
        """
        ptrs = []
        i = start_addr
        
        while i < len(self.words):
            ptr = self.words[i]
            i += 1
            
            # Check for terminator
            if ptr == self.DISPLAY_LIST_TERMINATOR or ptr < 0 or ptr >= len(self.words):
                break
            
            ptrs.append(ptr)
            
            if len(ptrs) > 1000:  # Safety limit
                break
        
        return ptrs
    
    def _read_polygon_entry(self, start_addr: int) -> Optional[PolygonEntry]:
        """
        Parse a single polygon entry from the display list
        
        Entry format:
        - length (1 word) - count of following words, including one trailing word
        - quad_index (1 word)
        - vertex_count (1 word)
        - depth_bias (1 word)
        - vertices (vertex_count * 3 words) - x, y, z coords
        - quad_count (1 word)
        - quads (quad_count * 5 words) - 4 vertex indices + color code
        
        Args:
            start_addr: Address where this entry starts
            
        Returns:
            PolygonEntry or None if parsing fails
        """
        i = start_addr
        
        try:
            # Read header
            if i < 0 or i + 3 >= len(self.words):
                return None
            
            length = self._unsigned16(self.words[i])
            i += 1
            
            if length <= 0 or length > 10000:
                return None
            
            quad_index = self._unsigned16(self.words[i])
            i += 1
            vertex_count = self._unsigned16(self.words[i])
            i += 1
            depth_bias = self._signed16(self.words[i])
            i += 1
            
            # Sanity checks
            if not (0 < vertex_count < self.MAX_VERTICES_PER_ENTRY):
                if self.verbose:
                    print(f"  Warning: suspicious vertex_count {vertex_count} at offset {start_addr}")
                return None
            
            # Read vertices
            vertices = []
            for v_idx in range(vertex_count):
                if i + 2 >= len(self.words):
                    if self.verbose:
                        print(f"  Warning: ran out of ROM data reading vertices at {start_addr}")
                    return None
                
                x = self._signed16(self.words[i])
                y = self._signed16(self.words[i + 1])
                z = self._signed16(self.words[i + 2])
                i += 3
                
                vertices.append(Vertex(x, y, z))
            
            # Read quad count
            if i >= len(self.words):
                return None
            
            quad_count = self._unsigned16(self.words[i])
            i += 1
            
            if self.verbose:
                print(f"  Polygon at {start_addr}: {vertex_count} verts, quad_count={quad_count}")
            
            if not (0 <= quad_count < self.MAX_QUADS_PER_ENTRY):
                if self.verbose:
                    print(f"    Warning: suspicious quad_count {quad_count}, treating as 0")
                # Don't fail entry, just skip quads
                quad_count = 0

            expected_length = 4 + 3 * vertex_count + 1 + 5 * quad_count
            if length != expected_length:
                if self.verbose:
                    print(f"    Warning: entry length {length} does not match counts (expected {expected_length})")
                return None
            if start_addr + length + 1 > len(self.words):
                if self.verbose:
                    print(f"    Warning: polygon entry at {start_addr} extends beyond ROM bounds")
                return None
            
            # Read quads
            quads = []
            
            for q_idx in range(quad_count):
                if i + 4 >= len(self.words):
                    if self.verbose:
                        print(f"    Warning: ran out of ROM data reading quad {q_idx}")
                    break
                
                v0 = self._unsigned16(self.words[i])
                v1 = self._unsigned16(self.words[i + 1])
                v2 = self._unsigned16(self.words[i + 2])
                v3 = self._unsigned16(self.words[i + 3])
                color = self._unsigned16(self.words[i + 4])
                i += 5
                
                # Validate vertex indices - just skip obviously bad ones
                vertex_indices = [v0, v1, v2, v3]
                if any(idx < 0 or idx >= vertex_count for idx in vertex_indices):
                    if self.verbose and q_idx < 3:
                        print(f"    Quad {q_idx}: INVALID indices {vertex_indices} (max={vertex_count-1})")
                    continue
                
                quads.append(Quad(color, tuple(vertex_indices)))
            
            return PolygonEntry(
                quad_index=quad_index,
                vertices=vertices,
                quads=quads,
                depth_bias=depth_bias
            )
        
        except (IndexError, ValueError) as e:
            if self.verbose:
                print(f"  Error parsing polygon entry at {start_addr}: {e}")
            return None
    
    def extract_model(self, object_index: int) -> Optional[List[PolygonEntry]]:
        """
        Extract a complete model (all polygon entries)
        
        Args:
            object_index: Index into address table
            
        Returns:
            List of PolygonEntry objects, or None if not found
        """
        if object_index < 0 or object_index >= len(self.address_table):
            if self.verbose:
                print(f"✗ Object index {object_index} out of range (0-{len(self.address_table)-1})")
            return None
        
        obj_addr = self.address_table[object_index]
        display_list = self._read_display_list(obj_addr)
        
        if self.verbose:
            print(f"✓ Object {object_index}: found {len(display_list)} polygon entries")
        
        model = []
        for ptr_idx, ptr in enumerate(display_list):
            poly = self._read_polygon_entry(ptr)
            if poly:
                model.append(poly)
            else:
                if self.verbose and ptr_idx < 5:
                    print(f"  Warning: failed to parse polygon entry {ptr_idx} at address {ptr}")
        
        return model if model else None
    
    def extract_all_models(self) -> Dict[int, List[PolygonEntry]]:
        """Extract all valid models from the ROM"""
        models = {}
        
        for obj_idx in range(len(self.address_table)):
            model = self.extract_model(obj_idx)
            if model:
                models[obj_idx] = model
                if self.verbose:
                    total_verts = sum(len(entry.vertices) for entry in model)
                    total_quads = sum(len(entry.quads) for entry in model)
                    print(f"  {obj_idx:3d}: {len(model):3d} poly entries, {total_verts:5d} verts, {total_quads:5d} quads")
        
        return models


class OBJExporter:
    """Export polygon data to Wavefront OBJ format"""

    @staticmethod
    def _normalize_pinched_face(indices: Tuple[int, ...]) -> Tuple[int, ...]:
        normalized = []
        for index in indices:
            if not normalized or index != normalized[-1]:
                normalized.append(index)
        if len(normalized) > 1 and normalized[0] == normalized[-1]:
            normalized.pop()
        return tuple(normalized)

    @staticmethod
    def _palette_pen(color_code: int) -> int:
        """Map a Starblade quad color code to a MAME palette pen."""
        color_code &= 0xFFFF
        code = color_code >> 8
        color = color_code & 0xFF
        if code & 0x80:
            return 0x2100 | color
        pen = 0x3E00 | color
        if (code & 0x02) == 0:
            pen |= 0x100
        return pen
    
    @staticmethod
    def write_obj(model: List[PolygonEntry], filename: str, 
                  scale: float = 1.0, center: bool = True,
                  palette: List[Tuple[int, int, int]] = None,
                  triangulate_pinched: bool = False) -> bool:
        """
        Export a model to OBJ format with MTL material file for colors
        
        Args:
            model: List of PolygonEntry objects
            filename: Output file path
            scale: Scale factor for coordinates
            center: Center model at origin
            palette: Optional palette list of (R, G, B) tuples for color lookup
            
        Returns:
            True if successful
        """
        # Consolidate all vertices from all entries
        all_vertices = []
        all_quads = []
        
        vertex_offset = 0
        
        for entry in model:
            for vertex in entry.vertices:
                all_vertices.append(vertex)
            
            for quad in entry.quads:
                # Remap vertex indices per entry
                remapped = tuple(idx + vertex_offset for idx in quad.vertices)
                all_quads.append((quad.color, remapped))
            
            vertex_offset += len(entry.vertices)
        
        if not all_vertices:
            print(f"✗ Model has no vertices")
            return False
        
        # Build unique color list
        unique_colors = set()
        for color, _ in all_quads:
            unique_colors.add(color)
        unique_colors = sorted(list(unique_colors))
        color_to_material = {color: f"mat_{i:03d}" for i, color in enumerate(unique_colors)}
        
        # Optional: compute bounds and center
        if center:
            xs = [v.x for v in all_vertices]
            ys = [v.y for v in all_vertices]
            zs = [v.z for v in all_vertices]
            
            center_x = (max(xs) + min(xs)) / 2.0
            center_y = (max(ys) + min(ys)) / 2.0
            center_z = (max(zs) + min(zs)) / 2.0
        else:
            center_x = center_y = center_z = 0.0
        
        # Create MTL filename (same base as OBJ)
        mtl_filename = os.path.splitext(filename)[0] + '.mtl'
        mtl_basename = os.path.basename(mtl_filename)
        
        # Write MTL file
        try:
            with open(mtl_filename, 'w') as f:
                f.write("# Starblade Model Materials\n\n")
                
                for color in unique_colors:
                    pen = OBJExporter._palette_pen(color)
                    if palette is not None and pen < len(palette):
                        r, g, b = palette[pen]
                    else:
                        r = g = b = 179
                    r_norm = r / 255.0
                    g_norm = g / 255.0
                    b_norm = b / 255.0
                    
                    mat_name = color_to_material[color]
                    f.write(f"newmtl {mat_name}\n")
                    f.write(f"Kd {g_norm:.6f} {r_norm:.6f} {b_norm:.6f} \n") # color order is actually GRB
                    f.write(f"Ka 0.0 0.0 0.0\n")
                    f.write(f"Ks 0.0 0.0 0.0\n\n")
        
        except IOError as e:
            print(f"✗ Failed to write MTL file: {e}")
            return False
        
        # Write OBJ file
        try:
            with open(filename, 'w') as f:
                f.write("# Starblade Model Export\n")
                f.write(f"# Vertices: {len(all_vertices)}\n")
                f.write(f"# Quads: {len(all_quads)}\n")
                f.write(f"# Unique colors: {len(unique_colors)}\n\n")
                f.write(f"mtllib {mtl_basename}\n\n")
                
                # Write vertices
                for v in all_vertices:
                    x = (v.x - center_x) * scale / 32.0  # Divide by 32 for reasonable scale
                    y = (v.y - center_y) * scale / 32.0
                    z = (v.z - center_z) * scale / 32.0
                    f.write(f"v {x:.6f} {y:.6f} {z:.6f}\n")
                
                f.write("\n")
                
                # Write quads with material assignment
                current_material = None
                for color, (v0, v1, v2, v3) in all_quads:
                    mat_name = color_to_material[color]
                    
                    # Switch material when color changes
                    if mat_name != current_material:
                        f.write(f"usemtl {mat_name}\n")
                        current_material = mat_name
                    
                    face_indices = (v0, v1, v2, v3)
                    if triangulate_pinched:
                        face_indices = OBJExporter._normalize_pinched_face(face_indices)
                    if len(face_indices) < 3:
                        continue

                    # OBJ uses 1-indexed vertices
                    f.write(f"# Color {hex(color)}\n")
                    obj_indices = " ".join(str(index + 1) for index in face_indices)
                    f.write(f"f {obj_indices}\n")
            
            print(f"✓ Exported {len(all_vertices)} vertices, {len(all_quads)} quads ({len(unique_colors)} colors) to {filename}")
            return True
        
        except IOError as e:
            print(f"✗ Failed to write OBJ file: {e}")
            return False


class Videoscape3DG1Exporter:
    """Export meshes to Videoscape 3DG1 text format."""

    @staticmethod
    def write_model(model: List[PolygonEntry], filename: str,
                    palette: List[Tuple[int, int, int]] = None,
                    triangulate_pinched: bool = False) -> bool:
        vertices = []
        faces = []
        vertex_offset = 0

        for entry in model:
            vertices.extend(entry.vertices)
            for quad in entry.quads:
                indices = quad.vertices
                if triangulate_pinched:
                    indices = OBJExporter._normalize_pinched_face(indices)
                if len(indices) < 3:
                    continue

                pen = OBJExporter._palette_pen(quad.color)
                if palette is not None and pen < len(palette):
                    red, green, blue = palette[pen]
                else:
                    red = green = blue = 179
                bgr = (blue << 16) | (red << 8) | green # order is actually GRB (or here BRG because reversed when written to file)
                faces.append((tuple(index + vertex_offset for index in indices), bgr))
            vertex_offset += len(entry.vertices)

        if not vertices:
            print("✗ Model has no vertices")
            return False

        try:
            with open(filename, 'w', encoding='ascii', newline='\n') as output:
                output.write("3DG1\n")
                output.write(f"{len(vertices)}\n")
                for vertex in vertices:
                    output.write(f"{vertex.x} {vertex.y} {vertex.z}\n")
                for indices, bgr in faces:
                    index_text = " ".join(str(index) for index in indices)
                    output.write(f"{len(indices)} {index_text} 0x{bgr:06X}\n")
                output.write("\x1a")

            print(f"✓ Exported {len(vertices)} points, {len(faces)} faces to {filename}")
            return True
        except IOError as e:
            print(f"✗ Failed to write 3DG1 file: {e}")
            return False


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Extract 3D models from Starblade System 21 Point ROMs"
    )
    parser.add_argument(
        "-b", "--bank",
        type=int,
        default=0,
        choices=[0, 1],
        help="Compatibility selector; Starblade banks are loaded as one address space (default: 0)"
    )
    parser.add_argument(
        "-o", "--object",
        type=int,
        default=None,
        help="Extract specific object by index (if not specified, lists all objects)"
    )
    parser.add_argument(
        "-d", "--directory",
        default="roms",
        help="Directory containing ROM files (default: roms/)"
    )
    parser.add_argument(
        "-O", "--output",
        default=None,
        help="Output file (default extension depends on --format)"
    )
    parser.add_argument(
        "-f", "--format",
        choices=["obj", "3dg1"],
        default="obj",
        help="Export format: Wavefront OBJ or Videoscape 3DG1 text"
    )
    parser.add_argument(
        "--triangulate-pinched",
        action="store_true",
        help="Convert faces with repeated adjacent vertices into triangles"
    )
    parser.add_argument(
        "-a", "--all",
        action="store_true",
        help="Export all objects in the address table"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output"
    )
    parser.add_argument(
        "--scale",
        type=float,
        default=1.0,
        help="Scale factor for exported coordinates"
    )
    parser.add_argument(
        "-p", "--palette",
        default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "starblad_Palette.bin"),
        help="Palette dump (4-byte B,R,G,unused entries; defaults to starblad_Palette.bin beside this script)"
    )
    
    args = parser.parse_args()
    
    # Load ROM
    print(f"Starblade Model Dumper v1.0")
    print(f"=" * 60)
    print("Loading Starblade point ROM address space...")
    
    rom = StarbladePointROM(args.directory, args.bank, args.verbose)
    
    if not rom.load_rom_bank():
        sys.exit(1)
    
    if not rom.parse_address_table():
        sys.exit(1)
    
    # Load palette if specified
    if args.palette:
        if not rom.load_palette(args.palette):
            print("Warning: Failed to load palette, colors will use default mapping")
    
    # Export
    if args.all:
        print(f"\nExtracting all models...")
        models = rom.extract_all_models()
        
        output_dir = "models"
        os.makedirs(output_dir, exist_ok=True)
        extension = "obj" if args.format == "obj" else "txt"
        
        for obj_idx, model in models.items():
            output_file = os.path.join(output_dir, f"model_bank{args.bank}_{obj_idx:03d}.{extension}")
            if args.format == "3dg1":
                Videoscape3DG1Exporter.write_model(
                    model, output_file, palette=rom.palette or None,
                    triangulate_pinched=args.triangulate_pinched)
            else:
                OBJExporter.write_obj(
                    model, output_file, args.scale, palette=rom.palette or None,
                    triangulate_pinched=args.triangulate_pinched)
    
    elif args.object is not None:
        print(f"\nExtracting object {args.object}...")
        model = rom.extract_model(args.object)
        
        if not model:
            print(f"✗ Failed to extract object {args.object}")
            sys.exit(1)
        
        if args.output is None:
            extension = "obj" if args.format == "obj" else "txt"
            args.output = f"model_bank{args.bank}_{args.object:03d}.{extension}"
        
        if args.format == "3dg1":
            success = Videoscape3DG1Exporter.write_model(
                model, args.output, palette=rom.palette or None,
                triangulate_pinched=args.triangulate_pinched)
        else:
            success = OBJExporter.write_obj(
                model, args.output, args.scale, palette=rom.palette or None,
                triangulate_pinched=args.triangulate_pinched)
        if not success:
            sys.exit(1)
    
    else:
        print(f"\nAvailable objects in address table:")
        print(f"Object index range: 0 to {len(rom.address_table) - 1}")
        print(f"Total address table entries: {len(rom.address_table)}")
        print(f"\nTo extract a specific object, use: -o <index>")
        print(f"To extract all objects, use: -a")


if __name__ == "__main__":
    main()

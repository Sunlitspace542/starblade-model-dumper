# starblade-model-dumper
Model dumper script for Starblade's NAMCO System 21 point ROMs.  
  
To use: ``python3 starblade_model_dumper.py [options]``  
  
```
usage: starblade_model_dumper.py [-h] [-b {0,1}] [-o OBJECT] [-d DIRECTORY] [-O OUTPUT] [-f {obj,3dg1}]
                                 [--triangulate-pinched] [-a] [-v] [--scale SCALE] [-p PALETTE]

Extract 3D models from Starblade System 21 Point ROMs

options:
  -h, --help            show this help message and exit
  -b, --bank {0,1}      Compatibility selector; Starblade banks are loaded as one address space (default: 0)
  -o, --object OBJECT   Extract specific object by index (if not specified, lists all objects)
  -d, --directory DIRECTORY
                        Directory containing ROM files (default: roms/)
  -O, --output OUTPUT   Output file (default extension depends on --format)
  -f, --format {obj,3dg1}
                        Export format: Wavefront OBJ or Videoscape 3DG1 text
  --triangulate-pinched
                        Convert faces with repeated adjacent vertices into triangles
  -a, --all             Export all objects in the address table
  -v, --verbose         Enable verbose output
  --scale SCALE         Scale factor for exported coordinates
  -p, --palette PALETTE
                        Palette dump (4-byte B,R,G,unused entries; defaults to starblad_Palette.bin beside this
                        script)
```
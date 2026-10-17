"""Reproducible CC0 RobCraft visual models. Blender 4.2+; metres, Z-up source.

Run: blender -b -noaudio --python scripts/blender/generate_robcraft_assets.py
Visual silhouettes represent robot classes, not approved vendor products.
"""

from pathlib import Path
import bpy
import math

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "robcraft" / "public" / "assets" / "robots"
OUT.mkdir(parents=True, exist_ok=True)
ENV_OUT = ROOT / "robcraft" / "public" / "assets" / "environment"
ENV_OUT.mkdir(parents=True, exist_ok=True)


def material(name, color, metallic=0.0, roughness=0.5, emission=None):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = next(node for node in mat.node_tree.nodes if node.type == 'BSDF_PRINCIPLED')
    bsdf.inputs['Base Color'].default_value = (*color, 1)
    bsdf.inputs['Metallic'].default_value = metallic
    bsdf.inputs['Roughness'].default_value = roughness
    if emission:
        bsdf.inputs['Emission Color'].default_value = (*color, 1)
        bsdf.inputs['Emission Strength'].default_value = emission
    mat.diffuse_color = (*color, 1)
    return mat


dark = material('graphite powder coat', (.045, .07, .075), .55, .42)
steel = material('brushed structural steel', (.25, .34, .37), .76, .3)
teal = material('teal composite shell', (.055, .48, .43), .16, .38)
ivory = material('service ivory polymer', (.68, .8, .76), .06, .4)
amber = material('safety amber', (.95, .48, .055), .18, .36)
glass = material('sensor lens', (.035, .16, .19), .35, .18)
signal = material('status LED', (.12, .88, .65), .0, .28, 1.8)
rubber = material('black rubber', (.018, .025, .028), .05, .83)


def box(name, xyz, size, mat, bevel=0.0):
    bpy.ops.mesh.primitive_cube_add(size=1, location=xyz)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(mat)
    if bevel:
        modifier = obj.modifiers.new('machined edges', 'BEVEL')
        modifier.width = bevel
        modifier.segments = 2
        obj.modifiers.new('weighted normals', 'WEIGHTED_NORMAL')
    return obj


def wheel(name, x, y, radius=.16, width=.1):
    bpy.ops.mesh.primitive_cylinder_add(vertices=12, radius=radius, depth=width,
                                        location=(x, y, radius))
    obj = bpy.context.object
    obj.name = name
    obj.rotation_euler[1] = math.pi / 2
    obj.data.materials.append(rubber)
    return obj


def base():
    box('low chassis', (0, 0, .29), (1.02, 1.34, .36), dark, .12)
    box('top cover', (0, -.08, .49), (.82, 1.04, .09), teal, .08)
    box('front LIDAR glass', (0, .68, .34), (.66, .035, .16), glass, .025)
    box('front LED bar', (0, .706, .43), (.53, .025, .028), signal, .008)
    box('rear bumper', (0, -.69, .24), (.88, .08, .11), rubber, .035)
    for x in (-.43, .43):
        for y in (-.43, .43):
            wheel('drive wheel', x, y)
    for x in (-.38, .38):
        box('side safety reflector', (x, .16, .48), (.025, .29, .045), amber, .009)


def pallet_amr():
    base()
    box('pallet deck', (0, -.04, .58), (1.02, 1.12, .09), steel, .035)
    for x in (-.38, .38):
        box('fork guide', (x, .15, .65), (.12, .67, .035), dark, .01)
    box('lift tower', (0, -.48, .75), (.2, .2, .46), dark, .025)
    box('warning beacon', (0, -.48, 1.01), (.11, .11, .1), signal, .024)


def forklift():
    base()
    box('operatorless lift housing', (0, -.25, .88), (.69, .65, .91), teal, .1)
    box('sensor fascia', (0, .09, .88), (.56, .05, .32), glass, .03)
    for x in (-.47, .47):
        box('mast rail', (x, .54, 1.05), (.085, .1, 1.43), steel, .025)
        box('fork', (x, .92, .34), (.12, .95, .07), steel, .02)
    box('lift crossbar', (0, .55, 1.53), (1.04, .11, .1), amber, .012)
    box('lift beacon', (0, -.48, 1.4), (.13, .13, .13), signal, .035)


def cleaning():
    base()
    box('cleaning tank', (0, -.2, .72), (.72, .8, .55), ivory, .12)
    box('service hatch', (0, -.21, 1.01), (.49, .47, .035), teal, .02)
    box('scrubber head', (0, .53, .14), (1.18, .34, .1), steel, .04)
    for x in (-.35, .35):
        box('front brush', (x, .76, .12), (.25, .22, .065), rubber, .02)
    box('water sensor', (0, .23, .9), (.24, .05, .15), glass, .01)


def medical_cart():
    base()
    box('sterile cabinet', (0, -.06, .98), (.78, .86, 1.0), ivory, .08)
    for z in (.73, 1.06, 1.39):
        box('sealed drawer', (0, .38, z), (.64, .038, .25), steel, .012)
        box('drawer grip', (0, .41, z), (.18, .016, .025), dark, .004)
    box('status display', (0, .24, 1.63), (.4, .04, .13), glass, .01)
    box('status light', (0, -.42, 1.54), (.11, .1, .11), signal, .022)


def rack_module():
    """1.2 m wide, 1 m deep, 2.6 m high; origin at the floor."""
    for x in (-.54, .54):
        for y in (-.44, .44):
            box('rack upright', (x, y, 1.30), (.07, .08, 2.6), blue, .008)
            box('rack foot plate', (x, y, .025), (.17, .17, .05), steel, .005)
    for level in (.28, 1.38, 2.46):
        for y in (-.45, .45):
            box('safety orange beam', (0, y, level), (1.19, .085, .105), amber, .012)
        box('ventilated steel shelf', (0, 0, level + .055), (1.09, .89, .035), steel, .005)
    for z in (.83, 1.93):
        box('carton on rack', (-.24, 0, z), (.43, .62, .74), cardboard, .018)
        box('carton on rack', (.25, 0, z), (.43, .62, .74), cardboard, .018)
        for x in (-.24, .25):
            box('carton seam', (x, -.315, z + .10), (.31, .006, .014), wood, .002)
    for x in (-.56, .56):
        box('height warning marker', (x, -.445, .21), (.012, .014, .32), paint, .003)


def pallet_load():
    """1.2 × 0.8 m pallet and wrapped box load, origin at the floor."""
    for y in (-.29, 0, .29):
        box('pallet bearer', (0, y, .075), (1.16, .12, .15), wood, .006)
    for x in (-.43, -.14, .15, .44):
        box('pallet deck plank', (x, 0, .17), (.25, .79, .045), wood, .005)
    for x in (-.29, .29):
        for y in (-.18, .18):
            box('boxed goods', (x, y, .46), (.53, .34, .51), cardboard, .022)
            box('box tape', (x, y - .174, .46), (.055, .007, .48), paint, .002)
    for x in (-.35, .35):
        box('shipping band', (x, 0, .73), (.025, .75, .025), dark, .002)


def charger_station():
    """1 × 1 m robot charging bay, floor origin, 0.68 m high."""
    box('charge floor tray', (0, 0, .045), (.98, .96, .09), dark, .025)
    for x in (-.37, .37):
        box('wheel positioning rail', (x, .08, .095), (.07, .62, .09), amber, .015)
    box('power pedestal', (0, -.34, .38), (.64, .20, .59), blue, .05)
    box('power pedestal cap', (0, -.34, .69), (.68, .24, .045), steel, .012)
    box('status screen', (0, -.224, .48), (.37, .014, .16), glass, .008)
    box('charging status bar', (0, -.214, .60), (.29, .011, .025), signal, .004)
    for x in (-.24, .24):
        box('contact plate', (x, -.21, .18), (.12, .045, .12), steel, .008)


def export(name, build, output=OUT):
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    build()
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.export_scene.gltf(filepath=str(output / f'{name}.glb'), export_format='GLB',
                              use_selection=True, export_apply=True, export_lights=False,
                              export_cameras=False, export_yup=True)
    mesh_count = sum(obj.type == 'MESH' for obj in bpy.context.scene.objects)
    face_count = sum(len(obj.data.polygons) for obj in bpy.context.scene.objects if obj.type == 'MESH')
    print(f'{name}: {mesh_count} parts, {face_count} faces, {(output / (name + ".glb")).stat().st_size} bytes')


if __name__ == '__main__':
    bpy.context.scene.unit_settings.system = 'METRIC'
    for name, build in [('pallet-amr', pallet_amr), ('forklift', forklift),
                        ('cleaning-robot', cleaning), ('medical-cart', medical_cart)]:
        export(name, build)
    wood = material('sealed pallet timber', (.38, .25, .12), .0, .78)
    cardboard = material('kraft corrugated board', (.56, .42, .25), .0, .86)
    blue = material('warehouse blue powder coat', (.07, .22, .37), .48, .46)
    paint = material('white safety marking', (.82, .87, .75), .06, .64)
    for name, build in [('rack-module', rack_module), ('pallet-load', pallet_load),
                        ('charger-station', charger_station)]:
        export(name, build, ENV_OUT)

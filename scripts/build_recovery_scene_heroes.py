"""Build original, detailed static GLB hero assets for the three SceneModels.

Run inside Blender 5.x: exec(open('scripts/build_recovery_scene_heroes.py', encoding='utf-8').read())
All parts are intentionally unparented and exported Z-up for the existing SceneRenderer3D adapter.
"""

import bpy
from pathlib import Path
from math import pi
import hashlib
import json


OUT = Path(__file__).resolve().parents[1] / 'frontend' / 'public' / 'scene-assets'
OUT.mkdir(parents=True, exist_ok=True)


def material(name, color, metal=0.0, rough=.55, emission=0.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    node = next(n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    node.inputs['Base Color'].default_value = (*color, 1)
    node.inputs['Metallic'].default_value = metal
    node.inputs['Roughness'].default_value = rough
    if emission:
        node.inputs['Emission Color'].default_value = (*color, 1)
        node.inputs['Emission Strength'].default_value = emission
    return mat


def reset():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)


def cube(name, center, size, mat, bevel=0):
    bpy.ops.mesh.primitive_cube_add(size=1, location=center)
    ob = bpy.context.object
    ob.name = name
    ob.dimensions = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    ob.data.materials.append(mat)
    if bevel:
        mod = ob.modifiers.new('Machined edges', 'BEVEL')
        mod.width = bevel
        mod.segments = 3
        ob.modifiers.new('Weighted normals', 'WEIGHTED_NORMAL')
    return ob


def cyl(name, center, radius, depth, mat, vertices=20, rotation=(0, 0, 0)):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=depth, location=center, rotation=rotation)
    ob = bpy.context.object
    ob.name = name
    ob.data.materials.append(mat)
    ob.modifiers.new('Weighted normals', 'WEIGHTED_NORMAL')
    return ob


def export(name):
    bpy.ops.object.select_all(action='SELECT')
    for ob in bpy.context.selected_objects:
        if ob.type == 'MESH':
            bpy.context.view_layer.objects.active = ob
            for mod in list(ob.modifiers):
                bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.ops.export_scene.gltf(filepath=str(OUT / f'{name}.glb'), export_format='GLB',
                              export_yup=False, export_apply=True, export_cameras=False,
                              export_lights=False)
    print(name, len([o for o in bpy.context.scene.objects if o.type == 'MESH']), (OUT / f'{name}.glb').stat().st_size)


steel = material('Powder coated steel midnight blue', (.045, .15, .25), .75, .31)
steel_light = material('Brushed galvanized steel', (.45, .54, .59), .82, .28)
orange = material('Industrial orange enamel', (.91, .31, .035), .36, .31)
yellow = material('Safety yellow enamel', (.96, .66, .035), .30, .37)
rubber = material('Black wheel rubber', (.018, .025, .03), .0, .83)
glass = material('Dark laminated glass', (.035, .13, .18), .1, .14)
white = material('Medical ivory polymer', (.79, .87, .85), .07, .39)
blue = material('Medical teal polymer', (.035, .43, .47), .16, .32)
timber = material('Pallet timber warm', (.52, .31, .13), .0, .84)
cardboard = material('Corrugated cardboard', (.55, .38, .22), .0, .91)
warning = material('Signal lamp amber', (1.0, .48, .025), .0, .25, 1.4)
red = material('Stop lamp red', (.78, .025, .02), .0, .26, 1.2)


# Warehouse rack: uprights, cross braces, three load-bearing decks, pallets and varied cartons.
reset()
for x in (-1.2, 1.2):
    for y in (-.48, .48):
        cube('Rack upright', (x, y, 1.65), (.09, .09, 3.3), steel, .012)
        cube('Foot plate', (x, y, .035), (.25, .25, .07), steel_light, .01)
for z in (.95, 1.95, 2.95):
    for y in (-.47, .47):
        cube('Orange load beam', (0, y, z), (2.43, .095, .15), orange, .012)
    for x in (-.85, 0, .85):
        cube('Deck cross member', (x, 0, z), (.055, 1.0, .075), steel_light, .006)
for x in (-1.19, 1.19):
    for z in (.64, 1.56, 2.48):
        brace = cube('Diagonal frame brace', (x, 0, z), (.045, 1.22, .055), steel_light)
        brace.rotation_euler[0] = .48 if z != 1.56 else -.48
for tier, z in enumerate((1.08, 2.08, 3.08)):
    for bay, x in enumerate((-.64, .64)):
        cube('Pallet slatted base', (x, 0, z), (1.02, .80, .10), timber, .012)
        for plank in (-.29, 0, .29):
            cube('Pallet bearer', (x, plank, z-.075), (.98, .085, .065), timber, .006)
        if not (tier == 2 and bay == 1):
            height = (.46, .67, .37)[(tier+bay)%3]
            cube('Wrapped carton load', (x, 0, z+.09+height/2), (.86, .68, height), cardboard, .035)
            cube('Carton seam', (x, 0, z+.09+height), (.86, .045, .008), timber)
for x in (-1.22, 1.22):
    cube('Safety end protector', (x, -.58, .23), (.20, .19, .46), yellow, .025)
export('hero_warehouse_rack')


# Pallet AMR: bevelled chassis, perimeter bumper, wheels, sensor and lit status.
reset()
cube('AMR load deck', (0, 0, .68), (1.48, 1.04, .15), steel_light, .06)
cube('AMR body shell', (0, 0, .37), (1.49, 1.03, .47), orange, .18)
cube('AMR black perimeter bumper', (0, 0, .19), (1.55, 1.09, .16), rubber, .07)
cube('AMR front fascia', (0, -.52, .39), (1.16, .05, .23), glass, .025)
for x in (-.56, .56):
    for y in (-.42, .42):
        cyl('AMR rubber wheel', (x, y, .20), .19, .12, rubber, 28, (pi/2, 0, 0))
        cyl('AMR wheel hub', (x, y - .065 if y < 0 else y + .065, .20), .095, .015, steel_light, 24, (pi/2, 0, 0))
    cube('AMR amber front light', (x, -.53, .53), (.17, .026, .07), warning, .014)
cyl('AMR lidar plinth', (0, 0, .78), .18, .075, rubber, 32)
cyl('AMR lidar rotating head', (0, 0, .88), .125, .12, glass, 32)
cube('AMR status strip', (0, .525, .55), (.55, .023, .045), blue, .01)
export('hero_pallet_amr')


# Robotic forklift: recognisable lifting mast, forks, chassis, beacon and lamps.
reset()
cube('Forklift body', (0, .13, .63), (1.37, 1.40, .84), orange, .16)
cube('Forklift cab roof', (0, .10, 1.83), (1.30, 1.20, .15), steel, .045)
for x in (-.55, .55):
    for y in (-.39, .56):
        cube('Forklift cab pillar', (x, y, 1.38), (.07, .07, .85), steel_light, .012)
for x in (-.54, .54):
    cyl('Forklift tire', (x, .50, .25), .24, .16, rubber, 28, (pi/2, 0, 0))
    cyl('Forklift steer tire', (x, -.49, .20), .18, .14, rubber, 28, (pi/2, 0, 0))
    cube('Forklift mast rail', (x, -.83, 1.27), (.095, .11, 2.37), steel_light, .015)
    cube('Forklift telescopic rail', (x, -.88, 1.47), (.05, .06, 1.82), steel, .007)
    cube('Fork tine', (x, -1.29, .22), (.13, 1.10, .065), steel_light, .013)
for z in (.37, 1.25, 2.25):
    cube('Forklift mast crossbar', (0, -.86, z), (1.14, .08, .10), steel, .01)
cyl('Forklift beacon', (0, .14, 1.99), .12, .13, warning, 24)
for x in (-.48, .48):
    cube('Forklift headlamp', (x, -.68, 1.06), (.15, .045, .12), white, .02)
export('hero_robot_forklift')


# Airport tug: low towing body with cab glazing, wheels, tow coupling and livery.
reset()
cube('Tug lower chassis', (0, 0, .38), (2.65, 1.34, .48), steel, .16)
cube('Tug yellow body', (0, .10, .64), (2.36, 1.24, .46), yellow, .14)
cube('Tug glazed cabin', (-.44, .16, 1.15), (1.09, 1.11, .67), glass, .11)
cube('Tug cab roof', (-.44, .16, 1.53), (1.20, 1.20, .10), white, .035)
for x in (-.80, .80):
    for y in (-.60, .60):
        cyl('Tug heavy tire', (x, y, .27), .275, .15, rubber, 28, (pi/2, 0, 0))
        cyl('Tug wheel rim', (x, y-.083 if y < 0 else y+.083, .27), .13, .018, steel_light, 24, (pi/2, 0, 0))
cube('Tug front impact bumper', (1.34, 0, .31), (.14, 1.42, .22), rubber, .045)
cube('Tug rear tow beam', (-1.48, 0, .34), (.50, .21, .13), steel_light, .025)
cyl('Tug coupling pin', (-1.70, 0, .30), .09, .24, steel_light, 18)
for y in (-.46, .46):
    cube('Tug headlight', (1.27, y, .74), (.045, .16, .11), white, .012)
    cube('Tug tail light', (-1.23, y, .70), (.043, .16, .10), red, .012)
cyl('Tug beacon', (-.44, .16, 1.66), .105, .17, warning, 24)
export('hero_airport_tug')


# Clinic delivery robot: rounded enclosed service shell, shelves, doors and sensors.
reset()
cube('Clinic mobile base', (0, 0, .22), (.78, .82, .34), blue, .11)
cube('Clinic sealed service body', (0, 0, .93), (.73, .74, 1.17), white, .12)
cube('Clinic upper cap', (0, 0, 1.58), (.80, .79, .16), blue, .065)
for z in (.58, 1.00, 1.40):
    cube('Clinic tray face', (0, -.386, z), (.55, .035, .30), glass, .024)
    cube('Clinic tray pull', (0, -.412, z-.11), (.26, .028, .025), steel_light, .01)
for x in (-.31, .31):
    for y in (-.32, .32):
        cyl('Clinic caster wheel', (x, y, .10), .09, .08, rubber, 20, (pi/2, 0, 0))
    cube('Clinic side protection', (x, 0, .38), (.055, .66, .12), rubber, .025)
cube('Clinic camera window', (0, -.38, 1.55), (.36, .03, .075), glass, .016)
for x in (-.20, .20):
    cyl('Clinic proximity sensor', (x, -.405, .30), .043, .015, glass, 16, (pi/2, 0, 0))
cube('Clinic status LED', (0, .39, 1.52), (.36, .02, .045), blue, .012)
export('hero_clinic_delivery')


# Architectural surrounds sit at the rear and left edges of each scene, leaving all routes untouched.
concrete = material('Warm industrial concrete', (.34, .39, .39), .0, .91)
wall_blue = material('Airport panel blue', (.18, .27, .36), .28, .55)
wall_clinic = material('Clinic clean wall', (.72, .82, .81), .0, .63)
dark_trim = material('Architectural dark trim', (.045, .08, .11), .52, .39)
light_strip = material('Linear luminaire diffuser', (.80, .91, .91), .0, .26, .8)


def shell(width, length, height, wall, trim, bay, title):
    reset()
    # A half-open two-wall set frames the scene but cannot conceal the route or moving robot.
    cube('Rear wall structural base', (width/2, length-.18, height/2), (width, .36, height), wall, .07)
    cube('Left wall structural base', (.18, length/2, height/2), (.36, length, height), wall, .07)
    cube('Rear wall dark plinth', (width/2, length-.39, .32), (width, .08, .64), trim)
    cube('Left wall dark plinth', (.39, length/2, .32), (.08, length, .64), trim)
    for x in range(0, int(width)+1, bay):
        cube('Steel rear wall pier', (x, length-.51, height/2), (.28, .28, height), steel_light, .025)
        cube('Overhead beam', (x, length*.78, height-.18), (.24, length*.44, .36), trim, .02)
        cube('Luminaire', (x, length*.65, height-.42), (.13, 2.6, .07), light_strip, .01)
    for y in range(0, int(length)+1, bay):
        cube('Side wall pier', (.49, y, height/2), (.28, .28, height), steel_light, .025)
    for x in range(bay//2, int(width)-bay//2, bay):
        cube('Wall service panel', (x, length-.56, 3.0), (bay*.68, .06, 3.6), trim, .025)
        cube('Wall high glazing', (x, length-.62, 6.65), (bay*.68, .06, 1.75), glass, .02)
        cube('Window transom', (x, length-.67, 5.77), (bay*.7, .05, .09), steel_light)
        cube('Window mid mullion', (x, length-.68, 6.65), (.06, .05, 1.72), steel_light)
    for y in range(bay//2, int(length)-bay//2, bay):
        cube('Wall lateral inset', (.56, y, 4.1), (.06, bay*.68, 4.1), trim, .025)
    cube('Roof edge beam rear', (width/2, length-.58, height-.05), (width, .56, .28), steel, .02)
    cube('Roof edge beam side', (.58, length/2, height-.05), (.56, length, .28), steel, .02)
    export(title)


shell(60, 40, 8.5, concrete, dark_trim, 10, 'hero_warehouse_shell')
shell(76, 48, 8.2, wall_blue, dark_trim, 12, 'hero_airport_shell')
shell(45, 28, 6.2, wall_clinic, blue, 7, 'hero_clinic_shell')

ASSETS = {
    'hero_warehouse_rack': 'pallet_rack', 'hero_pallet_amr': 'pallet_amr',
    'hero_robot_forklift': 'forklift_robot', 'hero_airport_tug': 'airport_tug',
    'hero_clinic_delivery': 'indoor_delivery_robot',
    'hero_warehouse_shell': 'warehouse environment',
    'hero_airport_shell': 'airport environment',
    'hero_clinic_shell': 'clinic environment',
}
manifest = {
    'schema_version': 'recovery-scene-assets-v1',
    'author': 'OpenAI Codex for ROBODOVOD',
    'license': 'Original procedural geometry made for this project',
    'source': 'scripts/build_recovery_scene_heroes.py',
    'assets': [
        {'asset_id': name, 'replaces_or_extends': target, 'file': f'{name}.glb',
         'bytes': (OUT / f'{name}.glb').stat().st_size,
         'sha256': hashlib.sha256((OUT / f'{name}.glb').read_bytes()).hexdigest()}
        for name, target in ASSETS.items()
    ],
}
(OUT / 'recovery-manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

"""Render an inspection sheet from the four generated GLB class models."""

from pathlib import Path
import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / 'robcraft' / 'public' / 'assets' / 'robots'
OUTPUT = ROOT / 'docs' / 'planning' / 'robodovod-robot-classes-2026-10-17.png'

bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)

for index, name in enumerate(('pallet-amr', 'forklift', 'cleaning-robot', 'medical-cart')):
    before = set(bpy.context.scene.objects)
    bpy.ops.import_scene.gltf(filepath=str(ASSETS / f'{name}.glb'))
    for obj in set(bpy.context.scene.objects) - before:
        if obj.type in {'MESH', 'EMPTY'}:
            obj.location.x += (index - 1.5) * 2.5

bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, -.09))
floor = bpy.context.object
floor.name = 'preview floor'
floor.dimensions = (11, 5, .18)
floor.data.materials.append(bpy.data.materials.new('preview ground'))
floor.data.materials[0].diffuse_color = (.06, .10, .10, 1)

bpy.ops.object.camera_add(location=(7, -14, 6.1))
camera = bpy.context.object
direction = Vector((0, 0, .55)) - camera.location
camera.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()
bpy.context.scene.camera = camera
camera.data.type = 'ORTHO'
camera.data.ortho_scale = 11.6

for location, power, size in [((-5, -4, 7), 1900, 5), ((5, 1, 6), 1500, 5)]:
    bpy.ops.object.light_add(type='AREA', location=location)
    bpy.context.object.data.energy = power
    bpy.context.object.data.shape = 'DISK'
    bpy.context.object.data.size = size

scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.samples = 24
scene.render.resolution_x = 1600
scene.render.resolution_y = 700
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'
scene.render.filepath = str(OUTPUT)
scene.world.color = (.2, .2, .2)
bpy.ops.render.render(write_still=True)
print(f'Preview: {OUTPUT} ({OUTPUT.stat().st_size} bytes)')

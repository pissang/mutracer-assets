# Generates sources/halloween.glb, the autumn night scene used by the
# Halloween Night example. All geometry is procedural and released under CC0 together
# with this script. Repeated props are linked meshes, so the file stores them once.
#
# Usage: /Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup \
#          -P scripts/create-halloween-scene.py
import math
import os
import random

import bpy
import numpy as np
from mathutils import Euler, Matrix, Vector, noise

OUTPUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'sources', 'halloween.glb')
rng = random.Random(1031)
noise.seed_set(31)
collection = bpy.context.scene.collection
for existing in list(bpy.data.objects):
    bpy.data.objects.remove(existing)


# --- Materials ---------------------------------------------------------------
def material(name, color=(1, 1, 1), rough=0.8, metal=0.0, emit=None, strength=1.0, glass=0.0, ior=1.5, coat=0.0,
             specular=0.5, two_sided=False):
    result = bpy.data.materials.new(name)
    result.use_nodes = True
    result.use_backface_culling = not two_sided
    inputs = result.node_tree.nodes['Principled BSDF'].inputs
    inputs['Base Color'].default_value = (*color, 1)
    inputs['Roughness'].default_value = rough
    inputs['Metallic'].default_value = metal
    inputs['IOR'].default_value = ior
    inputs['Transmission Weight'].default_value = glass
    inputs['Coat Weight'].default_value = coat
    inputs['Specular IOR Level'].default_value = specular
    if emit:
        inputs['Emission Color'].default_value = (*emit, 1)
        inputs['Emission Strength'].default_value = strength
    return result


M = {
    'ground': material('ground', rough=0.95, specular=0.15),
    'dark_stone': material('dark_stone', (0.05, 0.05, 0.055), 0.7),
    'bark': material('bark', rough=0.9),
    'pumpkin': material('pumpkin', (1.0, 0.3, 0.025), 0.42, coat=0.25),
    'flesh': material('flesh', (1.0, 0.48, 0.08), 0.75),
    'stem': material('stem', (0.16, 0.2, 0.05), 0.85),
    'iron': material('iron', (0.035, 0.035, 0.04), 0.28, 0.9),
    'water': material('water', (0.004, 0.006, 0.008), 0.02, ior=1.33),
    'crystal': material('crystal', (1, 1, 1), 0.0, glass=1.0, ior=1.6),
    'mirror': material('mirror', (0.96, 0.96, 0.97), 0.008, 1.0),
    'granite': material('granite', (0.006, 0.006, 0.008), 0.05, coat=1.0),
    'rust': material('rust', (0.09, 0.05, 0.035), 0.75, 0.6),
    'gold': material('gold', (1.0, 0.72, 0.3), 0.22, 1.0),
    'wood': material('wood', rough=0.75),
    'siding': material('siding', (0.3, 0.2, 0.14), 0.75),
    'trim': material('trim', (0.1, 0.06, 0.05), 0.7),
    'shingle': material('shingle', (0.035, 0.03, 0.05), 0.65),
    'window': material('window', (0.1, 0.05, 0.01), 0.4, emit=(1.0, 0.42, 0.07), strength=4.5),
    'window_dim': material('window_dim', (0.02, 0.02, 0.03), 0.08),
    'wax': material('wax', (0.85, 0.8, 0.62), 0.5),
    'flame': material('flame', emit=(1.0, 0.55, 0.14), strength=24),
    'fire': material('fire', emit=(1.0, 0.22, 0.03), strength=1.1),
    'brew': material('brew', (0.05, 0.3, 0.03), 0.15, emit=(0.2, 1.0, 0.15), strength=3.5),
    'bubble': material('bubble', (0.75, 1.0, 0.7), 0.0, glass=1.0, ior=1.33),
    'glass_red': material('glass_red', (0.85, 0.05, 0.08), 0.02, glass=1.0),
    'glass_green': material('glass_green', (0.15, 0.85, 0.25), 0.02, glass=1.0),
    'glass_purple': material('glass_purple', (0.45, 0.12, 0.9), 0.02, glass=1.0),
    'glass_clear': material('glass_clear', (0.95, 0.95, 0.9), 0.0, glass=1.0),
    'cork': material('cork', (0.4, 0.25, 0.12), 0.9),
    'bone': material('bone', (0.72, 0.66, 0.5), 0.55),
    'ghost': material('ghost', (0.8, 0.92, 1.0), 0.12, emit=(0.5, 0.75, 1.0), strength=0.06, glass=0.92, two_sided=True),
    'black': material('black', (0.006, 0.006, 0.008), 0.45),
    'feather': material('feather', (0.01, 0.01, 0.018), 0.3),
    'eye': material('eye', emit=(1.0, 0.8, 0.1), strength=9),
    'web': material('web', (0.8, 0.8, 0.85), 0.5),
    'fabric': material('fabric', (0.05, 0.02, 0.09), 0.75),
    'leaf_a': material('leaf_a', (0.78, 0.13, 0.012), 0.5, two_sided=True),
    'leaf_b': material('leaf_b', (0.5, 0.025, 0.018), 0.5, two_sided=True),
    'leaf_c': material('leaf_c', (0.9, 0.36, 0.025), 0.5, two_sided=True),
    'grass': material('grass', (0.1, 0.13, 0.04), 0.7, two_sided=True),
    'mushroom': material('mushroom', (0.6, 0.06, 0.04), 0.4),
    'text': material('text', (0.02, 0.02, 0.022), 0.8),
    'hill': material('hill', (0.02, 0.02, 0.05), 0.9),
    'pine': material('pine', (0.012, 0.018, 0.04), 0.9),
}


# --- Stone textures: tileable because the noise is filtered white noise --------
def tile_noise(size, falloff, seed):
    frequencies = np.fft.fftfreq(size) * size
    radius = np.hypot(*np.meshgrid(frequencies, frequencies))
    radius[0, 0] = 1
    white = np.random.default_rng(seed).normal(size=(size, size))
    field = np.fft.ifft2(np.fft.fft2(white) / radius ** falloff).real
    return (field - field.min()) / (field.max() - field.min())


def pack_image(name, rgb, colorspace):
    size = rgb.shape[0]
    image = bpy.data.images.new(name, size, size, alpha=False)
    image.colorspace_settings.name = colorspace
    image.pixels.foreach_set(np.dstack((rgb, np.ones((size, size)))).astype(np.float32).ravel())
    image.pack()
    return image


def stone_material(size=512):
    large, fine = tile_noise(size, 1.5, 1), tile_noise(size, 0.75, 2)
    pits = np.clip((tile_noise(size, 0.55, 3) - 0.62) * 9, 0, 1)
    height = large * 0.8 + fine * 0.2 - pits * 0.08
    shade = 0.36 + 0.3 * large + 0.16 * fine - 0.14 * pits
    lichen = np.clip((tile_noise(size, 0.95, 4) - 0.7) * 16, 0, 1)[..., None] * np.clip(fine * 2, 0, 1)[..., None]
    albedo = shade[..., None] * np.array((1.0, 0.97, 0.91)) * (1 - lichen) + lichen * np.array((0.52, 0.52, 0.28))
    dx = (np.roll(height, -1, 1) - np.roll(height, 1, 1)) * 13
    dy = (np.roll(height, -1, 0) - np.roll(height, 1, 0)) * 13
    length = np.sqrt(dx * dx + dy * dy + 1)
    normal = np.dstack((-dx / length, -dy / length, 1 / length)) * 0.5 + 0.5
    result = material('stone', rough=0.82)
    nodes, links = result.node_tree.nodes, result.node_tree.links
    bsdf = nodes['Principled BSDF']
    color = nodes.new('ShaderNodeTexImage')
    color.image = pack_image('stone_color', np.clip(albedo, 0, 1), 'sRGB')
    links.new(color.outputs['Color'], bsdf.inputs['Base Color'])
    bump = nodes.new('ShaderNodeTexImage')
    bump.image = pack_image('stone_normal', normal, 'Non-Color')
    normal_map = nodes.new('ShaderNodeNormalMap')
    links.new(bump.outputs['Color'], normal_map.inputs['Color'])
    links.new(normal_map.outputs['Normal'], bsdf.inputs['Normal'])
    return result


M['stone'] = stone_material()


# --- Geometry: (vertices, faces) tuples, merged before becoming a mesh --------
def merge(*parts):
    verts, faces = [], []
    for part_verts, part_faces in parts:
        start = len(verts)
        verts.extend(part_verts)
        faces.extend(tuple(i + start for i in face) for face in part_faces)
    return verts, faces


def xf(part, loc=(0, 0, 0), rot=(0, 0, 0), scale=1):
    scale = (scale,) * 3 if isinstance(scale, (int, float)) else scale
    matrix = Matrix.LocRotScale(Vector(loc), Euler(rot), Vector(scale))
    return [matrix @ Vector(v) for v in part[0]], part[1]


def box(w, d, h):
    """Box centered in XY with its base at z = 0."""
    x, y = w / 2, d / 2
    verts = [(-x, -y, 0), (x, -y, 0), (x, y, 0), (-x, y, 0), (-x, -y, h), (x, -y, h), (x, y, h), (-x, y, h)]
    return verts, [(3, 2, 1, 0), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]


def surface(fn, around, along):
    """Closed revolution-like surface. fn(u, v) with v in 0..1 runs bottom pole to top pole."""
    verts = [Vector(fn(0, 0))]
    for j in range(1, along):
        verts.extend(Vector(fn(i / around, j / along)) for i in range(around))
    verts.append(Vector(fn(0, 1)))
    top = len(verts) - 1
    index = lambda i, j: 1 + (j - 1) * around + i % around
    faces = [(0, index(i + 1, 1), index(i, 1)) for i in range(around)]
    faces += [(top, index(i, along - 1), index(i + 1, along - 1)) for i in range(around)]
    for j in range(1, along - 1):
        faces += [(index(i, j), index(i + 1, j), index(i + 1, j + 1), index(i, j + 1)) for i in range(around)]
    return verts, faces


def lathe(profile, around=32):
    """Revolves (radius, z) points. Ends at radius 0 are closed; others are left open."""
    verts, faces = [], []
    for r, z in profile:
        verts.extend((r * math.cos(2 * math.pi * i / around), r * math.sin(2 * math.pi * i / around), z)
                     for i in range(around))
    for j in range(len(profile) - 1):
        for i in range(around):
            a, b = j * around + i, j * around + (i + 1) % around
            faces.append((a, b, b + around, a + around))
    return verts, faces


def sphere(r=1.0, around=20, along=12):
    return surface(lambda u, v: (r * math.sin(v * math.pi) * math.cos(u * math.tau),
                                 r * math.sin(v * math.pi) * math.sin(u * math.tau),
                                 -r * math.cos(v * math.pi)), around, along)


def tube(points, radii, sides=8):
    """Sweeps a circle along points with parallel-transported frames and closed ends."""
    points = [Vector(p) for p in points]
    if isinstance(radii, (int, float)):
        radii = [radii] * len(points)
    verts, faces = [], []
    tangent = (points[1] - points[0]).normalized()
    side = tangent.orthogonal().normalized()
    for k, point in enumerate(points):
        next_tangent = (points[min(k + 1, len(points) - 1)] - points[max(k - 1, 0)]).normalized()
        side = (side - next_tangent * side.dot(next_tangent)).normalized()
        other = next_tangent.cross(side)
        verts.extend(point + (side * math.cos(i / sides * math.tau) + other * math.sin(i / sides * math.tau)) * radii[k]
                     for i in range(sides))
    for k in range(len(points) - 1):
        for i in range(sides):
            a, b = k * sides + i, k * sides + (i + 1) % sides
            faces.append((a, b, b + sides, a + sides))
    faces.append(tuple(range(sides - 1, -1, -1)))
    faces.append(tuple((len(points) - 1) * sides + i for i in range(sides)))
    return verts, faces


def prism(outline, depth):
    """Extrudes an (x, z) outline along Y, centered on y = 0. Clockwise outlines are reversed."""
    n = len(outline)
    area = sum(outline[i][0] * outline[(i + 1) % n][1] - outline[(i + 1) % n][0] * outline[i][1] for i in range(n))
    outline = outline if area > 0 else outline[::-1]
    verts = [(x, -depth / 2, z) for x, z in outline] + [(x, depth / 2, z) for x, z in outline]
    faces = [tuple(range(n)), tuple(range(2 * n - 1, n - 1, -1))]
    faces += [(i, n + i, n + (i + 1) % n, (i + 1) % n) for i in range(n)]
    return verts, faces


def fbm(x, y, z=0.0, octaves=3):
    total, amplitude, scale = 0.0, 0.5, 1.0
    for _ in range(octaves):
        total += noise.noise(Vector((x * scale, y * scale, z * scale))) * amplitude
        amplitude, scale = amplitude * 0.5, scale * 2.1
    return total


def rough_up(part, amount, scale):
    """Displaces vertices by noise, for weathered stone and wood."""
    return [Vector(v) + Vector((fbm(*(Vector(v) * scale)), fbm(*(Vector(v) * scale + Vector((7, 3, 1)))),
                                fbm(*(Vector(v) * scale + Vector((2, 9, 5)))))) * amount for v in part[0]], part[1]


def surface_grid_box(w, d, h, cuts):
    """Box with subdivided sides, so noise displacement reads on its silhouette."""
    verts, faces, seen = [], [], {}

    def vertex(x, y, z):
        key = (round(x, 5), round(y, 5), round(z, 5))
        if key not in seen:
            seen[key] = len(verts)
            verts.append(key)
        return seen[key]

    axes = [((1, 0, 0), (0, 0, 1), (0, -1, 0)), ((0, 0, 1), (1, 0, 0), (0, 1, 0)), ((0, 1, 0), (0, 0, 1), (1, 0, 0)),
            ((0, 0, 1), (0, 1, 0), (-1, 0, 0)), ((0, 1, 0), (1, 0, 0), (0, 0, -1)), ((1, 0, 0), (0, 1, 0), (0, 0, 1))]
    half = Vector((w / 2, d / 2, h / 2))
    for u_axis, v_axis, normal in axes:
        u_axis, v_axis, normal = Vector(u_axis), Vector(v_axis), Vector(normal)
        grid = {}
        for i in range(cuts + 1):
            for j in range(cuts + 1):
                p = u_axis * (2 * i / cuts - 1) + v_axis * (2 * j / cuts - 1) + normal
                grid[i, j] = vertex(p.x * half.x, p.y * half.y, p.z * half.z + half.z)
        for i in range(cuts):
            for j in range(cuts):
                faces.append((grid[i, j], grid[i + 1, j], grid[i + 1, j + 1], grid[i, j + 1]))
    return verts, faces


# --- Objects -----------------------------------------------------------------
def make_mesh(name, part, mats, angle=40, paint=None):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata([tuple(v) for v in part[0]], [], part[1])
    mesh.validate()
    mesh.update()
    for mat in mats if isinstance(mats, (list, tuple)) else [mats]:
        mesh.materials.append(M[mat])
    if angle is None:
        mesh.shade_flat()
    else:
        mesh.shade_smooth()
        mesh.set_sharp_from_angle(angle=math.radians(angle))
    if paint:
        apply_paint(mesh, paint)
    return mesh


def apply_paint(mesh, paint):
    attribute = mesh.color_attributes.new('Col', 'FLOAT_COLOR', 'POINT')
    for vertex, datum in zip(mesh.vertices, attribute.data):
        datum.color = (*paint(vertex.co), 1)


def place(name, mesh, loc=(0, 0, 0), rot=(0, 0, 0), scale=1):
    result = bpy.data.objects.new(name, mesh)
    collection.objects.link(result)
    result.location = loc
    result.rotation_euler = rot
    result.scale = (scale,) * 3 if isinstance(scale, (int, float)) else scale
    return result


def add(name, part, mats, loc=(0, 0, 0), rot=(0, 0, 0), scale=1, angle=40, paint=None):
    return place(name, make_mesh(name, part, mats, angle, paint), loc, rot, scale)


def bake(obj):
    """Applies an object's modifiers to its mesh, dropping the modifiers."""
    bpy.context.view_layer.update()
    evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    baked = bpy.data.meshes.new_from_object(evaluated)
    obj.modifiers.clear()
    obj.data = baked
    return baked


def point_light(name, loc, color, power):
    light = bpy.data.lights.new(name, 'POINT')
    light.color = color
    light.energy = power
    return place(name, light, loc)


def gray(low, high, scale, offset=0.0):
    """Noise paint between two gray levels."""
    return lambda co: (lambda t: (t, t, t))(low + (high - low) * max(0, min(1, 0.5 + fbm(co.x * scale + offset, co.y * scale, co.z * scale) * 1.4)))


def tint(low, high, scale, offset=0.0):
    def paint(co):
        t = max(0, min(1, 0.5 + fbm(co.x * scale + offset, co.y * scale, co.z * scale) * 1.5))
        return tuple(a + (b - a) * t for a, b in zip(low, high))
    return paint


# --- Ground ------------------------------------------------------------------
def path_x(y):
    """Centerline of the footpath from the camera to the porch."""
    return 0.6 + 0.9 * math.sin(y * 0.33 + 0.4)


def smoothstep(a, b, x):
    t = max(0, min(1, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


# Standing water: center, radii. Their mirror angles catch the moon and the lit windows.
PUDDLES = [(-0.95, -4.35, 1.2, 1.05), (0.1, -0.4, 1.4, 1.35)]


def puddle_distance(x, y, puddle):
    cx, cy, rx, ry = puddle
    return math.hypot((x - cx) / rx, (y - cy) / ry) + fbm(x * 0.9, y * 0.9, 6.0) * 0.45


def ground_z(x, y):
    height = base_ground_z(x, y)
    for puddle in PUDDLES:
        height -= 0.16 * (1 - smoothstep(0.5, 1.1, puddle_distance(x, y, puddle)))
    return height


def surface_z(x, y):
    """Top of the ground or of the water covering it."""
    height = ground_z(x, y)
    for puddle in PUDDLES:
        height = max(height, base_ground_z(puddle[0], puddle[1]) - 0.05 if puddle_distance(x, y, puddle) < 1.1 else height)
    return height


def base_ground_z(x, y):
    height = fbm(x * 0.13, y * 0.13, 1.5) * 0.9 + fbm(x * 0.9, y * 0.9, 4.0, 2) * 0.05
    height *= 0.35 + 0.65 * smoothstep(3, 12, math.hypot(x, y + 3))
    height -= 0.05 * (1 - smoothstep(0.5, 1.1, abs(x - path_x(y)))) * (y < 11)
    height += smoothstep(18, 42, y) * 2.5 * (1 - smoothstep(3, 8, x)) + smoothstep(8, 13, y) * 1.5 * (1 - smoothstep(4, 8, x))
    height -= smoothstep(4, 8, x) * smoothstep(0, 5, y) * 9
    return height


def ground_paint(co):
    mud = fbm(co.x * 0.35, co.y * 0.35, 8.0)
    moss = max(0, min(1, 0.5 + mud * 3))
    grain = 0.75 + 0.25 * fbm(co.x * 3, co.y * 3, 2.0, 2) * 2
    color = [(0.085 + (0.07 - 0.085) * moss) * grain, (0.035 + (0.05 - 0.035) * moss) * grain,
             (0.018 + (0.018 - 0.018) * moss) * grain]
    on_path = (1 - smoothstep(0.45, 1.0, abs(co.x - path_x(co.y)))) * (co.y < 11)
    return tuple(c + (p - c) * on_path for c, p in zip(color, (0.075, 0.06, 0.05)))


grid = 120
verts = []
for j in range(grid + 1):
    for i in range(grid + 1):
        s, t = i / grid * 2 - 1, j / grid * 2 - 1
        x = math.copysign(abs(s) ** 1.7, s) * 60 + 0.5
        y = math.copysign(abs(t) ** 1.7, t) * 60 - 2 + (t > 0) * t * 10
        verts.append((x, y, ground_z(x, y)))
faces = [(j * (grid + 1) + i, j * (grid + 1) + i + 1, (j + 1) * (grid + 1) + i + 1, (j + 1) * (grid + 1) + i)
         for j in range(grid) for i in range(grid)]
add('ground', (verts, faces), 'ground', angle=89, paint=ground_paint)

for index, puddle in enumerate(PUDDLES):
    cx, cy, rx, ry = puddle
    outline = [(cx + 1.3 * rx * math.cos(a / 48 * math.tau), cy + 1.3 * ry * math.sin(a / 48 * math.tau), base_ground_z(cx, cy) - 0.05) for a in range(48)]
    add(f'puddle.{index}', (outline, [tuple(range(48))]), 'water', angle=None)

add('lake', ([(4, 0, -4.5), (130, 0, -4.5), (130, 100, -4.5), (4, 100, -4.5)], [(0, 1, 2, 3)]), 'water', angle=None)

for index in range(3):
    hill_x = -40 + index * 42
    add(f'hill.{index}', xf(sphere(1, 48, 16), (hill_x, 62 + index * 9, -4), (0, 0, 0), (34 + index * 7, 12, 11 + index * 2.2)),
        'hill', angle=80)

pine = make_mesh('pine', merge(*[xf(lathe([(0.0, 0), (1.05 - tier * 0.22, 0.05), (0.0, 1.5)], 8), (0, 0, tier * 0.85))
                                 for tier in range(4)]), 'pine', angle=65)
for index in range(60):
    x = rng.uniform(-48, 48)
    y = rng.uniform(40, 62)
    if x > 9 or abs(x - 1) < 14 and y < 48:
        continue
    place(f'pine.{index}', pine, (x, y, ground_z(x, y) + 2 * smoothstep(40, 62, y) - 0.2), (0, 0, rng.uniform(0, 6)),
          rng.uniform(1.8, 3.2))


# --- Jack-o'-lanterns --------------------------------------------------------
TRIANGLE_EYES = [
    [(-0.48, 0.14), (-0.13, 0.14), (-0.3, 0.46)],
    [(0.13, 0.14), (0.48, 0.14), (0.3, 0.46)],
    [(-0.08, -0.03), (0.08, -0.03), (0, 0.1)],
]
TOOTHY_MOUTH = [(-0.62, -0.1), (-0.42, -0.18), (-0.34, -0.08), (-0.22, -0.14), (-0.13, -0.05), (0.13, -0.05), (0.22, -0.14),
                (0.34, -0.08), (0.42, -0.18), (0.62, -0.1), (0.46, -0.42), (0.28, -0.53), (0.2, -0.4), (0.06, -0.4),
                (0.0, -0.58), (-0.06, -0.4), (-0.2, -0.4), (-0.28, -0.53), (-0.46, -0.42)]
ANGRY_EYES = [
    [(-0.5, 0.36), (-0.1, 0.1), (-0.42, 0.06)],
    [(0.5, 0.36), (0.42, 0.06), (0.1, 0.1)],
    [(-0.07, -0.08), (0.07, -0.08), (0, 0.05)],
]
ZIG_MOUTH = [(-0.56, -0.22), (-0.38, -0.3), (-0.28, -0.18), (-0.14, -0.3), (0, -0.18), (0.14, -0.3), (0.28, -0.18), (0.38, -0.3),
             (0.56, -0.22), (0.38, -0.5), (0.28, -0.4), (0.14, -0.52), (0, -0.4), (-0.14, -0.52), (-0.28, -0.4), (-0.38, -0.5)]
ROUND_EYES = [
    [(-0.28 + 0.15 * math.cos(a / 16 * math.tau), 0.22 + 0.17 * math.sin(a / 16 * math.tau)) for a in range(16)],
    [(0.28 + 0.15 * math.cos(a / 16 * math.tau), 0.22 + 0.17 * math.sin(a / 16 * math.tau)) for a in range(16)],
]
O_MOUTH = [(0.2 * math.cos(a / 20 * math.tau), -0.27 + 0.25 * math.sin(a / 20 * math.tau)) for a in range(20)]


def pumpkin(name, loc, radius, face, turn, ribs=11, light=2.5, squash=0.8):
    def shape(u, v):
        theta, phi = u * math.tau, v * math.pi
        rib = abs(math.sin(ribs * theta / 2 + 0.3)) ** 0.5
        wide = math.sin(phi) ** 0.8 * (0.87 + 0.13 * rib)
        return (wide * math.cos(theta), wide * math.sin(theta),
                squash * (-math.cos(phi)) * (1 - 0.22 * math.exp(-(wide / 0.34) ** 2)))

    def groove(co):
        theta = math.atan2(co.y, co.x)
        rib = abs(math.sin(ribs * theta / 2 + 0.3)) ** 0.5
        t = 0.45 + 0.55 * rib + 0.08 * fbm(co.x * 7, co.y * 7, co.z * 7)
        return (t, t * t, t * t)

    obj = add(name, surface(shape, 84, 42), ['pumpkin', 'flesh'], angle=38)
    shell = obj.modifiers.new('shell', 'SOLIDIFY')
    shell.thickness = 0.09
    shell.offset = -1
    shell.material_offset = 1
    bake(obj)
    # Prisms along -Y carve real holes through both walls of the front half.
    for k, outline in enumerate(face):
        cutter = add(f'{name}.cut.{k}', xf(prism(outline, 1.4), (0, -0.7, 0)), 'flesh')
        cut = obj.modifiers.new('cut', 'BOOLEAN')
        cut.operation = 'DIFFERENCE'
        cut.object = cutter
        cut.solver = 'EXACT'
        cut.material_mode = 'TRANSFER'
        bake(obj)
        bpy.data.objects.remove(cutter)
    obj.data.shade_smooth()
    obj.data.set_sharp_from_angle(angle=math.radians(38))
    apply_paint(obj.data, groove)
    rot = (0, 0, turn)
    center = Vector(loc) + Vector((0, 0, squash * radius * 0.97))
    obj.location, obj.rotation_euler, obj.scale = center, rot, (radius, radius, radius)

    stem_path = [(0, 0, squash * 0.72), (0.02, 0.01, squash * 0.95), (0.07, 0.02, squash * 1.14), (0.17, 0.03, squash * 1.27)]
    stem = tube(stem_path, [0.15, 0.1, 0.075, 0.07], 8)
    add(f'{name}.stem', stem, 'stem', center, rot, radius, angle=70)
    wick = lathe([(0.0, 0), (0.1, 0), (0.1, 0.2), (0.0, 0.2)], 12)
    add(f'{name}.candle', wick, 'wax', center + Vector((0, 0, -squash * radius * 0.82)), scale=radius, angle=50)
    flame = lathe([(0.0, 0), (0.05, 0.05), (0.06, 0.1), (0.03, 0.18), (0.0, 0.27)], 12)
    flame_z = -squash * radius * 0.82 + 0.21 * radius
    add(f'{name}.flame', flame, 'flame', center + Vector((0, 0, flame_z)), scale=radius, angle=80)
    point_light(f'{name}.light', center + Vector((0, 0, flame_z + radius * 0.34)), (1.0, 0.42, 0.08), light)


def ground_at(x, y, lift=0.0):
    return (x, y, ground_z(x, y) + lift)


def surface_at(x, y, lift=0.0):
    return (x, y, surface_z(x, y) + lift)


pumpkin('pumpkin.hero', ground_at(-2.9, -5.7, -0.05), 0.82, TRIANGLE_EYES + [TOOTHY_MOUTH], -0.2, light=2.4)
pumpkin('pumpkin.angry', ground_at(-1.55, -5.5, -0.03), 0.55, ANGRY_EYES + [ZIG_MOUTH], -0.05, ribs=9, light=1.1, squash=0.88)
pumpkin('pumpkin.surprised', ground_at(-0.6, -5.75, -0.02), 0.36, ROUND_EYES + [O_MOUTH], 0.1, ribs=8, light=0.5, squash=0.74)
# Its back to the camera, this one projects its face onto the wall in front of it.
pumpkin('pumpkin.projector', ground_at(5.05, -1.25, -0.02), 0.42, TRIANGLE_EYES + [TOOTHY_MOUTH], math.pi + 0.14, light=6)
wall = merge(rough_up(surface_grid_box(2.5, 0.34, 1.3, 16), 0.012, 3), xf(rough_up(surface_grid_box(2.62, 0.46, 0.08, 8), 0.012, 3), (0, 0, 1.3)))
add('wall', wall, 'stone', ground_at(5.05, -0.1, -0.08), (0, 0, 0.03), angle=70, paint=lambda co: (lambda t: (t, t, t))(0.6 + 0.4 * smoothstep(0, 0.7, co.z)))
# An uncarved pumpkin patch: linked copies of one solid pumpkin.
plain_ribs = 10


def plain_shape(u, v):
    theta, phi = u * math.tau, v * math.pi
    rib = abs(math.sin(plain_ribs * theta / 2)) ** 0.5
    wide = math.sin(phi) ** 0.8 * (0.87 + 0.13 * rib)
    return wide * math.cos(theta), wide * math.sin(theta), 0.78 * -math.cos(phi) * (1 - 0.22 * math.exp(-(wide / 0.34) ** 2))


plain = make_mesh('plain_pumpkin', surface(plain_shape, 70, 28), 'pumpkin', angle=60,
                  paint=lambda co: (lambda t: (t, t * t, t * t))(0.5 + 0.5 * abs(math.sin(plain_ribs * math.atan2(co.y, co.x) / 2)) ** 0.5))
plain_stem = make_mesh('plain_stem', tube([(0, 0, 0.55), (0.03, 0, 0.8), (0.1, 0.02, 1.0)], [0.14, 0.09, 0.07], 7), 'stem')
for index, (x, y, r) in enumerate([(-4.9, -2.2, 0.36), (-3.1, -1.5, 0.25), (-5.0, -1.2, 0.3), (1.9, -5.4, 0.22), (-1.6, -2.2, 0.27),
                                   (7.2, -2.0, 0.33), (7.8, -1.1, 0.24)]):
    loc = ground_at(x, y, 0.72 * r)
    turn = rng.uniform(0, 6)
    place(f'plain.{index}', plain, loc, (0.06, 0.05, turn), r)
    place(f'plain_stem.{index}', plain_stem, loc, (0.06, 0.05, turn), r)


# --- Dead trees --------------------------------------------------------------
def dead_tree(name, loc, height, seed, spread=0.55, depth=5, lean=0.04):
    local = random.Random(seed)
    parts, tips = [], []

    def branch(start, direction, length, radius, level):
        points, radii = [Vector(start)], [radius]
        current, heading = Vector(start), direction.normalized()
        steps = 3 + level
        for step in range(steps):
            heading = (heading + Vector((local.uniform(-0.3, 0.3), local.uniform(-0.3, 0.3), local.uniform(-0.15, 0.2)))).normalized()
            current = current + heading * (length / steps)
            points.append(current.copy())
            radii.append(radius * (1 - 0.62 * (step + 1) / steps))
        sides = max(4, min(14, int(radius * 55)))
        parts.append(tube(points, radii, sides))
        if level <= 1:
            tips.append((current.copy(), heading.copy(), radii[-1]))
            return
        for _ in range(local.choice((2, 3))):
            twist = local.uniform(0, math.tau)
            side = heading.orthogonal().normalized()
            side = side * math.cos(twist) + heading.cross(side) * math.sin(twist)
            child = (heading + side * local.uniform(spread * 0.7, spread * 1.5) + Vector((0, 0, 0.08))).normalized()
            branch(current, child, length * local.uniform(0.62, 0.8), radii[-1] * 0.92, level - 1)

    base_radius = height * 0.052
    branch(Vector((0, 0, -0.2)), Vector((lean, 0, 1)), height * 0.36, base_radius, depth)
    for index in range(7):
        angle = index / 7 * math.tau + local.uniform(-0.2, 0.2)
        out = Vector((math.cos(angle), math.sin(angle), 0))
        root = [Vector((0, 0, height * 0.09)) + out * base_radius * 0.2, Vector((0, 0, height * 0.02)) + out * base_radius * 1.5,
                out * base_radius * 3.2 + Vector((0, 0, -0.04)), out * base_radius * 5 + Vector((local.uniform(-.2, .2), local.uniform(-.2, .2), -0.25))]
        parts.append(tube(root, [base_radius * 0.5, base_radius * 0.35, base_radius * 0.17, 0.005], 8))
    obj = add(name, rough_up(merge(*parts), height * 0.008, 5 / height), 'bark', loc, angle=70,
              paint=tint((0.02, 0.016, 0.015), (0.09, 0.07, 0.06), 9 / height))
    return [(Vector(loc) + p, d, r) for p, d, r in tips]


hero_tips = dead_tree('tree.hero', ground_at(-6.3, -3.4), 7.6, 12, lean=0.3)
dead_tree('tree.right', ground_at(7.4, -2.6), 7.0, 45)
house_trees = [dead_tree('tree.back', ground_at(-7.5, 13.0), 8.5, 7, depth=4), dead_tree('tree.far', ground_at(7.0, 13.5), 7.0, 23, depth=4),
               dead_tree('tree.mid', ground_at(-5.5, 9.2), 5.2, 31, depth=4)]


# Maple foliage: linked clusters of many leaves, for every autumn crown.
MAPLE = [(0, -0.5), (0.07, -0.18), (0.32, -0.28), (0.26, -0.05), (0.5, 0.06), (0.3, 0.14), (0.36, 0.34), (0.14, 0.26), (0, 0.55),
         (-0.14, 0.26), (-0.36, 0.34), (-0.3, 0.14), (-0.5, 0.06), (-0.26, -0.05), (-0.32, -0.28), (-0.07, -0.18)]


def leaf_part(center, size):
    leaf = ([Vector((x, y, 0.08 * math.sin(y * 4))) for x, y in MAPLE], [tuple(range(len(MAPLE)))])
    return xf(leaf, center, (rng.uniform(-1.2, 1.2), rng.uniform(-1.2, 1.2), rng.uniform(0, math.tau)), size)


def leaf_cluster(name, mat, radius, count, size, flat=1.0):
    parts = [leaf_part(Vector((rng.gauss(0, radius), rng.gauss(0, radius), rng.gauss(0, radius * flat))), size * rng.uniform(0.7, 1.2)) for _ in range(count)]
    return make_mesh(name, merge(*parts), mat, angle=None)


clusters = [leaf_cluster(f'crown.{k}', ('leaf_a', 'leaf_b', 'leaf_c')[k % 3], 0.55, 50, 0.38) for k in range(6)]


def crown(name, tips, chance, scale=1.0):
    for k, (tip, _, _) in enumerate(tips):
        for j in range(3):
            if rng.random() < chance:
                offset = Vector((rng.gauss(0, 0.4), rng.gauss(0, 0.4), rng.gauss(0.1, 0.3))) * scale
                place(f'{name}.{k}.{j}', rng.choice(clusters), tip + offset, (rng.uniform(0, 6), rng.uniform(0, 6), rng.uniform(0, 6)), scale * rng.uniform(0.8, 1.35))


crown('crown.hero', hero_tips, 0.95, 1.15)
for k, tips in enumerate(house_trees):
    crown(f'crown.house.{k}', tips, 1.0, 0.95)


# --- Weathered stones and graves ---------------------------------------------
def arch_outline(w, h, n=14):
    r = w / 2
    points = [(-r, 0), (r, 0), (r, h - r)]
    points += [(r * math.cos(i / n * math.pi), h - r + r * math.sin(i / n * math.pi)) for i in range(1, n)]
    return points + [(-r, h - r)]


def cross_outline(w, h, arm=0.34):
    a, b, z0, z1 = arm * w / 2, w / 2, h * 0.58, h * 0.58 + arm * w
    return [(-a, 0), (a, 0), (a, z0), (b, z0), (b, z1), (a, z1), (a, h), (-a, h), (-a, z1), (-b, z1), (-b, z0), (-a, z0)]


stone_paint = tint((0.45, 0.45, 0.43), (0.8, 0.8, 0.78), 1.2)


def grave_paint(co):
    """Damp soil stain and moss creeping up from the base; the texture carries the detail."""
    light = 0.5 + 0.5 * smoothstep(0.0, 0.45, co.z)
    moss = 0.75 * smoothstep(0.0, 0.3, fbm(co.x * 2.2 + 4, co.y * 2.2, co.z * 2.2) - co.z * 0.3 + 0.12)
    return tuple(a + (b - a) * moss for a, b in zip((light, light, light * 0.98), (0.26, 0.36, 0.13)))


def stone_mesh(name, outline, depth, polished=False):
    obj = add(name, prism(outline, depth), 'granite' if polished else 'stone', angle=None)
    bevel = obj.modifiers.new('bevel', 'BEVEL')
    bevel.width = 0.012
    bevel.segments = 3
    bevel.limit_method = 'ANGLE'
    bake(obj)
    mesh = obj.data
    if not polished:
        remesh = obj.modifiers.new('remesh', 'REMESH')
        remesh.mode = 'VOXEL'
        remesh.voxel_size = 0.04
        bake(obj)
        mesh = obj.data
        for vertex in mesh.vertices:
            vertex.co += Vector((fbm(vertex.co.x * 3, vertex.co.y * 3, vertex.co.z * 3), fbm(vertex.co.x * 3 + 5, vertex.co.y * 3, vertex.co.z * 3),
                                 fbm(vertex.co.x * 3, vertex.co.y * 3 + 9, vertex.co.z * 3))) * 0.016
        apply_paint(mesh, grave_paint)
    mesh.shade_smooth()
    mesh.set_sharp_from_angle(angle=math.radians(30))
    bpy.data.objects.remove(obj)
    mesh.use_fake_user = True
    return mesh, depth


stones = {
    'arch': stone_mesh('grave_arch', arch_outline(0.75, 1.1), 0.16),
    'tall': stone_mesh('grave_tall', arch_outline(0.55, 1.45), 0.15),
    'cross': stone_mesh('grave_cross', cross_outline(0.75, 1.35), 0.14),
    'slab': stone_mesh('grave_slab', [(-0.42, 0), (0.42, 0), (0.42, 0.72), (0.2, 0.84), (-0.2, 0.84), (-0.42, 0.72)], 0.14),
    'polished': stone_mesh('grave_polished', arch_outline(0.66, 1.45), 0.15, polished=True),
}


def carve(kind, name, lines, fill):
    """Returns a copy of a stone mesh with lines of text cut into its front face."""
    source, depth = stones[kind]
    obj = place(name, source.copy())
    for k, (text, size, height) in enumerate(lines):
        curve = bpy.data.curves.new(f'{name}.{k}', 'FONT')
        curve.body = text
        curve.size = size
        curve.align_x = 'CENTER'
        curve.extrude = 0.009
        holder = bpy.data.objects.new(f'{name}.{k}', curve)
        collection.objects.link(holder)
        bpy.context.view_layer.update()
        cutter_mesh = bpy.data.meshes.new_from_object(holder.evaluated_get(bpy.context.evaluated_depsgraph_get()))
        bpy.data.objects.remove(holder)
        bpy.data.curves.remove(curve)
        cutter_mesh.materials.clear()
        cutter_mesh.materials.append(M[fill])
        cutter_mesh.transform(Matrix.LocRotScale(Vector((0, -depth / 2, height)), Euler((math.pi / 2, 0, 0)), None))
        cutter = place(f'{name}.cut.{k}', cutter_mesh)
        cut = obj.modifiers.new('cut', 'BOOLEAN')
        cut.operation = 'DIFFERENCE'
        cut.object = cutter
        cut.solver = 'EXACT'
        cut.material_mode = 'TRANSFER'
        bake(obj)
        bpy.data.objects.remove(cutter)
    mesh = obj.data
    mesh.shade_smooth()
    mesh.set_sharp_from_angle(angle=math.radians(30))
    if kind != 'polished':
        for attribute in list(mesh.color_attributes):
            mesh.color_attributes.remove(attribute)
        apply_paint(mesh, grave_paint)
    bpy.data.objects.remove(obj)
    return mesh


graves = [
    ('arch', -1.0, -0.6, 0.15, 0.04, [('R.I.P.', 0.17, 0.62), ('1693', 0.09, 0.45)]),
    ('polished', 3.0, -0.05, -0.04, -0.02, [('HERE', 0.1, 0.92), ('LIES', 0.1, 0.78), ('NOBODY', 0.075, 0.62)]),
    ('cross', -2.3, 1.1, 0.3, 0.12, []),
    ('slab', 3.4, 1.6, -0.1, 0.1, [('R.I.P.', 0.13, 0.46)]),
    ('arch', -3.4, 3.0, 0.2, -0.1, [('BOO', 0.16, 0.55)]),
    ('slab', -0.8, 2.9, 0.05, -0.12, [('REST', 0.1, 0.46)]),
    ('tall', 4.2, 3.8, -0.3, 0.05, [('1731', 0.1, 0.75)]),
    ('cross', 2.7, 3.5, 0.05, -0.16, []),
    ('arch', -1.7, 4.9, -0.15, 0.08, []),
    ('cross', -4.9, 5.0, 0.3, 0.05, []),
    ('slab', 4.9, 1.0, -0.4, 0.14, []),
    ('tall', 6.3, 3.4, -0.25, 0.1, []),
    ('arch', 3.8, 5.8, 0.1, 0.1, []),
    ('cross', -3.0, 6.0, 0.1, -0.1, []),
    ('slab', -6.2, 3.2, 0.25, -0.06, []),
    ('arch', 6.6, 0.8, -0.35, -0.08, []),
]
for index, (kind, x, y, turn, lean, lines) in enumerate(graves):
    if x > 5.5:  # Would stand in the lake.
        continue
    rot = (lean * 0.6, lean, turn)
    loc = ground_at(x, y, -0.07)
    mesh = carve(kind, f'grave.{index}', lines, 'gold' if kind == 'polished' else 'dark_stone') if lines else stones[kind][0]
    place(f'grave.{index}', mesh, loc, rot)
    add(f'grave.{index}.plot', xf(rough_up(surface_grid_box(0.8, 1.4, 0.14, 5), 0.05, 3), (0, -0.82, -0.05)), 'ground', loc, (0, 0, turn), angle=70,
        paint=tint((0.03, 0.022, 0.016), (0.055, 0.05, 0.025), 2.5))


# --- Iron fence and gate -----------------------------------------------------
picket = make_mesh('picket', merge(
    tube([(0, 0, -0.1), (0, 0, 1.35)], 0.012, 6),
    xf(lathe([(0.0, 0), (0.03, 0.03), (0.005, 0.15), (0.0, 0.15)], 6), (0, 0, 1.33)),
    xf(lathe([(0.0, -0.02), (0.022, 0), (0.0, 0.02)], 8), (0, 0, 1.28))), 'iron', angle=50)
rocks = [xf(box(0.3, 0.3, 1.6))]
for course in range(10):
    for side in range(8):
        angle = side / 8 * math.tau + course * 0.39
        rocks.append(xf(rough_up(sphere(1, 8, 5), 0.18, 2.2), (0.17 * math.cos(angle), 0.17 * math.sin(angle), 0.08 + course * 0.158), (0, 0, angle), (0.085, 0.085, 0.078)))
rocks.append(xf(rough_up(surface_grid_box(0.52, 0.52, 0.07, 3), 0.008, 5), (0, 0, 1.62)))
post = make_mesh('fence_post', merge(*rocks), 'stone', angle=55, paint=stone_paint)


def fence_run(start, end, name):
    start, end = Vector(start), Vector(end)
    span = end - start
    count = int(span.length / 0.17)
    rail_lo, rail_hi = [], []
    samples = max(2, int(span.length))
    for k in range(samples + 1):
        p = start + span * (k / samples)
        ground = ground_z(p.x, p.y)
        rail_lo.append((p.x, p.y, ground + 0.2))
        rail_hi.append((p.x, p.y, ground + 1.15))
    add(f'{name}.lo', tube(rail_lo, 0.016, 6), 'iron', angle=60)
    add(f'{name}.hi', tube(rail_hi, 0.016, 6), 'iron', angle=60)
    for k in range(count + 1):
        p = start + span * (k / count)
        place(f'{name}.{k}', picket, ground_at(p.x, p.y), (rng.uniform(-0.012, 0.012), rng.uniform(-0.02, 0.02), 0))
    place(f'{name}.post', post, ground_at(start.x, start.y, -0.1))
    place(f'{name}.post2', post, ground_at(end.x, end.y, -0.1))


GATE_Y = 7.6
gate_center = path_x(GATE_Y)
for k, (a, b) in enumerate([(-22, -14), (-14, -7), (-7, gate_center - 1.0), (gate_center + 1.0, 5)]):
    fence_run((a, GATE_Y, 0), (b, GATE_Y, 0), f'fence.{k}')
arch = [Vector((gate_center - 1.0 + 2 * i / 24, GATE_Y, 2.05 + 0.5 * math.sin(i / 24 * math.pi) + ground_z(gate_center, GATE_Y))) for i in range(25)]
add('gate.arch', tube(arch, 0.025, 8), 'iron', angle=70)
add('gate.arch2', tube([p + Vector((0, 0, 0.18)) for p in arch], 0.016, 6), 'iron', angle=70)
for k, sign in enumerate((-1, 1)):
    hinge = Vector((gate_center + sign * 1.0, GATE_Y, 0))
    leaf_dir = Vector((-sign * math.cos(1.05), -math.sin(1.05), 0))
    for i in range(1, 6):
        p = hinge + leaf_dir * (i * 0.17)
        place(f'gate.leaf.{k}.{i}', picket, ground_at(p.x, p.y, 0.1), (0, 0, 0), (1, 1, 1.15))
    add(f'gate.rail.{k}.lo', tube([hinge + Vector((0, 0, ground_z(hinge.x, hinge.y) + 0.45)), hinge + leaf_dir * 0.95 + Vector((0, 0, ground_z(hinge.x, hinge.y) + 0.42))], 0.016, 6), 'iron')
    add(f'gate.rail.{k}.hi', tube([hinge + Vector((0, 0, ground_z(hinge.x, hinge.y) + 1.3)), hinge + leaf_dir * 0.95 + Vector((0, 0, ground_z(hinge.x, hinge.y) + 1.27))], 0.016, 6), 'iron')

path_stone = make_mesh('path_stone', rough_up(xf(sphere(1, 12, 7), scale=(1, 0.85, 0.12)), 0.1, 1.6), 'stone', angle=70, paint=stone_paint)
y = -7.5
index = 0
while y < 11.0:
    x = path_x(y) + rng.uniform(-0.22, 0.22)
    place(f'path.{index}', path_stone, surface_at(x, y, 0.005), (0, 0, rng.uniform(0, 6)), rng.uniform(0.2, 0.34))
    y += rng.uniform(0.42, 0.58)
    index += 1


# --- Haunted house -----------------------------------------------------------
def build_house(origin):
    siding, trim, shingles, windows, dim = [], [], [], [], []
    W, D, H = 9.0, 6.0, 5.8

    def wall(cx, cy, length, height, angle, z0=0.0):
        rows = int(height / 0.26)
        for r in range(rows):
            wobble = rng.uniform(-0.012, 0.012)
            siding.append(xf(box(length + rng.uniform(0, 0.04), 0.07, 0.25), (cx, cy, z0 + r * 0.26), (0.11 + wobble, 0, angle)))

    wall(0, -D / 2, W, H, 0)
    wall(0, D / 2, W, H, math.pi)
    wall(-W / 2, 0, D, H, math.pi / 2 * 3)
    wall(W / 2, 0, D, H, math.pi / 2)
    trim.append(box(W - 0.2, D - 0.2, H + 0.1))
    # Gable roof: overlapping shingle courses on two pitched planes.
    pitch = 0.82
    span = (D / 2 + 0.55) / math.cos(pitch)
    courses = int(span / 0.28)
    for sign in (-1, 1):
        for c in range(courses):
            along = c * 0.28 + 0.14
            y = sign * (D / 2 + 0.55 - along * math.cos(pitch))
            z = H + 0.1 + along * math.sin(pitch)
            x = -W / 2 - 0.35
            while x < W / 2 + 0.35:
                width = rng.uniform(0.32, 0.5)
                shingles.append(xf(box(width - 0.02, 0.3, 0.035), (x + width / 2, y, z + rng.uniform(-0.012, 0.012)),
                                   (sign * pitch + rng.uniform(-0.05, 0.05) + (0.1 * sign), rng.uniform(-0.03, 0.03), rng.uniform(-0.03, 0.03))))
                x += width
    ridge = H + 0.1 + span * math.sin(pitch)
    for sign in (-1, 1):
        outline = [(-(D / 2 + 0.2), 0), (D / 2 + 0.2, 0), (0, span * math.sin(pitch) - 0.05)]
        trim.append(xf(prism(outline, 0.12), (sign * (W / 2 - 0.02), 0, H + 0.1), (0, 0, math.pi / 2)))
    trim.append(xf(box(W + 0.9, 0.16, 0.16), (0, 0, ridge - 0.03)))

    def window(x, y, z, angle, w=0.95, h=1.6, lit=True, boarded=False):
        (windows if lit else dim).append(xf(box(w, 0.04, h), (x, y, z), (0, 0, angle)))
        frame = Matrix.LocRotScale(Vector((x, y, z)), Euler((0, 0, angle)), None)
        offset = -0.04
        bars = [box(w + 0.2, 0.09, 0.09), xf(box(w + 0.2, 0.09, 0.09), (0, 0, h)), xf(box(0.09, 0.09, h), (-w / 2 - 0.05, 0, 0)),
                xf(box(0.09, 0.09, h), (w / 2 + 0.05, 0, 0)), xf(box(0.04, 0.07, h), (0, offset, 0)), xf(box(w, 0.07, 0.04), (0, offset, h * 0.55)),
                xf(box(w + 0.4, 0.2, 0.06), (0, offset, -0.06)), xf(lathe([(w / 2 + 0.17, 0), (w / 2 + 0.17, 0.03)], 4), (0, 0, h + 0.09), (0, 0, math.pi / 4))]
        for bar in bars:
            trim.append(([frame @ Vector(v) for v in bar[0]], bar[1]))
        if boarded:
            for b in range(3):
                board = xf(box(w + 0.35, 0.03, 0.14), (0, -0.09, h * (0.2 + b * 0.3)), (0, rng.uniform(-0.3, 0.3), 0))
                trim.append(([frame @ Vector(v) for v in board[0]], board[1]))

    front = -D / 2 - 0.08
    window(-3.0, front, 1.0, 0)
    window(3.0, front, 1.0, 0, lit=False, boarded=True)
    window(-3.0, front, 3.5, 0, lit=False)
    window(-1.0, front, 3.5, 0)
    window(1.0, front, 3.5, 0, lit=False, boarded=True)
    window(3.0, front, 3.5, 0)
    window(-W / 2 - 0.08, -1.2, 1.2, math.pi * 1.5)
    # Door and porch.
    door = merge(box(1.3, 0.1, 2.3), xf(box(0.08, 0.14, 2.3), (-0.65, 0, 0)), xf(box(0.08, 0.14, 2.3), (0.65, 0, 0)), xf(box(1.5, 0.14, 0.1), (0, 0, 2.3)))
    trim.append(xf(door, (0, front - 0.03, 0.3)))
    windows.append(xf(box(0.9, 0.04, 0.3), (0, front - 0.09, 2.2)))
    deck = merge(box(5.0, 2.0, 0.3), xf(box(2.2, 0.4, 0.2), (0, -1.15, 0)), xf(box(2.6, 0.45, 0.1), (0, -1.45, 0)))
    trim.append(xf(deck, (0, front - 1.0, 0)))
    for x in (-2.3, -0.9, 0.9, 2.3):
        trim.append(xf(lathe([(0.1, 0), (0.08, 0.2), (0.06, 0.3), (0.075, 1.2), (0.05, 2.1), (0.1, 2.3)], 10), (x, front - 1.85, 0.3)))
    porch_courses = 8
    for c in range(porch_courses):
        along = c * 0.28
        x = -2.8
        while x < 2.8:
            width = rng.uniform(0.32, 0.5)
            shingles.append(xf(box(width - 0.02, 0.3, 0.035), (x + width / 2, front - 2.2 + along * 0.92, 2.68 + along * 0.4), (-0.42, 0, rng.uniform(-0.03, 0.03))))
            x += width
    for k in range(9):
        trim.append(xf(box(0.04, 1.0, 0.04), (-2.0 + k * 0.5, front - 2.2 + 0.5, 2.62)))
    # Tower.
    tower_x, tower_y = W / 2 - 0.2, -D / 2 - 0.4
    tower_h = 8.8
    tower = lathe([(0.0, 0), (1.55, 0), (1.55, tower_h), (0.0, tower_h)], 8)
    trim.append(xf(tower, (tower_x, tower_y, 0), (0, 0, math.pi / 8)))
    for r in range(int(tower_h / 0.3)):
        siding.append(xf(lathe([(1.59, 0), (1.63, 0.0), (1.57, 0.29)], 8), (tower_x, tower_y, r * 0.3), (0, 0, math.pi / 8)))
    for a in range(8):
        angle = a / 8 * math.tau + math.pi * 1.5
        x, y = tower_x + 1.45 * math.cos(angle), tower_y + 1.45 * math.sin(angle)
        for z, lit in ((1.2, a in (1, 7)), (4.8, a in (0, 1, 7))):
            window(x, y, z, angle + math.pi / 2, 0.6, 1.6, lit=lit)
    trim.append(xf(lathe([(1.0, 0), (2.1, 0.02), (2.1, 0.1), (1.0, 0.12)], 8), (tower_x, tower_y, tower_h), (0, 0, math.pi / 8)))
    roof_profile = [(2.05, 0), (1.3, 1.4), (0.7, 2.9), (0.25, 4.5), (0.02, 5.8), (0.0, 5.82)]
    roof = xf(lathe(roof_profile, 8), (tower_x, tower_y, tower_h + 0.1), (0, 0, math.pi / 8))
    shingles.append(roof)
    trim.append(tube([(tower_x, tower_y, tower_h + 5.8), (tower_x, tower_y, tower_h + 6.6)], 0.02, 6))
    # Chimneys.
    for cx, cy, h in ((-2.8, 1.1, 2.9), (1.9, -0.8, 2.6)):
        chimney = merge(box(0.8, 0.7, h), xf(box(0.95, 0.85, 0.12), (0, 0, h)), xf(box(0.3, 0.3, 0.45), (-0.15, 0, h + 0.12)), xf(box(0.3, 0.3, 0.32), (0.2, 0, h + 0.12)))
        trim.append(xf(chimney, (cx, cy, ridge - 1.2)))
    place_parts = [('house.siding', siding, 'siding'), ('house.trim', trim, 'trim'), ('house.shingles', shingles, 'shingle'),
                   ('house.windows', windows, 'window'), ('house.dark_windows', dim, 'window_dim')]
    for name, parts, mat in place_parts:
        add(name, merge(*parts), mat, origin, (0.0, 0.012, 0.06), angle=None)


HOUSE = ground_at(0.3, 15.2, -0.12)
build_house(HOUSE)
point_light('house.interior', (HOUSE[0], HOUSE[1] - 5.4, HOUSE[2] + 1.8), (1.0, 0.5, 0.16), 5)
point_light('house.porch', (HOUSE[0], HOUSE[1] - 5.5, HOUSE[2] + 2.8), (1.0, 0.45, 0.14), 2)


# --- Skulls ------------------------------------------------------------------
def make_skull():
    head = merge(
        xf(sphere(1, 36, 24), (0, 0.06, 0.52), scale=(0.47, 0.56, 0.47)),
        xf(sphere(1, 20, 12), (0, -0.33, 0.16), scale=(0.3, 0.2, 0.25)),
        xf(sphere(1, 12, 10), (-0.18, -0.34, 0.4), scale=(0.13, 0.1, 0.09)),
        xf(sphere(1, 12, 10), (0.18, -0.34, 0.4), scale=(0.13, 0.1, 0.09)),
        xf(sphere(1, 16, 10), (0, -0.28, -0.06), scale=(0.22, 0.2, 0.1)),
    )
    obj = add('skull', head, 'bone')
    remesh = obj.modifiers.new('remesh', 'REMESH')
    remesh.mode = 'VOXEL'
    remesh.voxel_size = 0.036
    bake(obj)
    cutters = [xf(sphere(1, 14, 10), (-0.17, -0.49, 0.36), scale=(0.115, 0.14, 0.1)),
               xf(sphere(1, 14, 10), (0.17, -0.49, 0.36), scale=(0.115, 0.14, 0.1)),
               xf(lathe([(0.0, 0), (0.07, 0), (0.0, 0.14)], 8), (0, -0.54, 0.13), scale=(1, 1.7, 1))]
    for k, cutter_part in enumerate(cutters):
        cutter = add(f'skull.cut.{k}', cutter_part, 'bone')
        cut = obj.modifiers.new('cut', 'BOOLEAN')
        cut.operation = 'DIFFERENCE'
        cut.object = cutter
        cut.solver = 'EXACT'
        bake(obj)
        bpy.data.objects.remove(cutter)
    teeth = merge(*[xf(box(0.04, 0.04, 0.075), (-0.15 + i * 0.05, -0.49 + abs(i - 3) * 0.012, 0.0 - (i % 2) * 0.008)) for i in range(7)])
    obj.data.shade_smooth()
    skull_mesh = obj.data
    bpy.data.objects.remove(obj)
    skull_mesh.use_fake_user = True
    apply_paint(skull_mesh, gray(0.75, 1.0, 5))
    return skull_mesh, make_mesh('skull_teeth', teeth, 'bone', angle=30)


skull_mesh, teeth_mesh = make_skull()


def skull(name, loc, rot=(0, 0, 0), scale=0.2):
    place(name, skull_mesh, loc, rot, scale)
    place(f'{name}.teeth', teeth_mesh, loc, rot, scale)


skull('skull.hero', ground_at(0.65, -4.65, 0.02), (0.08, 0.1, -0.55), 0.2)
skull('skull.tree', ground_at(-3.8, 0.45, 0.0), (-0.15, 0.2, 0.75), 0.18)
skull('skull.grave', ground_at(-0.75, 1.9, -0.01), (0.02, -0.08, 0.4), 0.16)
bone = make_mesh('bone', merge(tube([(-0.4, 0, 0), (0.4, 0, 0)], 0.035, 8), xf(sphere(0.06, 10, 7), (-0.42, 0.03, 0)), xf(sphere(0.06, 10, 7), (-0.42, -0.03, 0)),
                               xf(sphere(0.06, 10, 7), (0.42, 0.03, 0)), xf(sphere(0.06, 10, 7), (0.42, -0.03, 0))), 'bone')
for index, (x, y, turn) in enumerate([(0.2, -5.1, 0.5), (1.0, -4.35, -0.4), (0.45, -4.2, 2.1), (-3.3, 0.7, 1.0), (-4.0, 0.0, 2.4)]):
    place(f'bone.{index}', bone, ground_at(x, y, 0.045), (0, rng.uniform(-0.06, 0.06), turn), 0.42)


# --- Witch's cauldron --------------------------------------------------------
CAULDRON = Vector(ground_at(3.0, -2.35))
pot_profile = [(0.0, 0.0), (0.26, 0.0), (0.46, 0.13), (0.56, 0.33), (0.56, 0.52), (0.46, 0.7), (0.43, 0.74), (0.49, 0.8), (0.47, 0.84), (0.39, 0.76),
               (0.48, 0.55), (0.48, 0.34), (0.38, 0.17), (0.0, 0.1)]
pot_base = Vector((0, 0, 0.34))
add('cauldron', lathe(pot_profile, 48), 'iron', CAULDRON + pot_base, angle=50)
for sign in (-1, 1):
    ring = [(sign * (0.56 + 0.08 * (1 - math.cos(a / 16 * math.tau))), 0, 0.42 + 0.09 * math.sin(a / 16 * math.tau)) for a in range(17)]
    add(f'cauldron.handle.{sign}', tube(ring, 0.018, 6), 'iron', CAULDRON + pot_base)
for k in range(3):
    a = k / 3 * math.tau + 0.4
    add(f'cauldron.leg.{k}', tube([(0.34 * math.cos(a), 0.34 * math.sin(a), 0.42), (0.42 * math.cos(a), 0.42 * math.sin(a), 0.1), (0.46 * math.cos(a), 0.46 * math.sin(a), 0)], [0.04, 0.03, 0.045], 8), 'iron', CAULDRON)


def brew_surface(u, v):
    radius = (1 - abs(2 * v - 1)) * 0.42
    theta = u * math.tau
    x, y = radius * math.cos(theta), radius * math.sin(theta)
    return x, y, (0.03 * fbm(x * 8, y * 8, 2, 2) if v > 0.5 else -0.02 * (1 - 2 * v))


add('cauldron.brew', surface(brew_surface, 40, 16), 'brew', CAULDRON + pot_base + Vector((0, 0, 0.78)), angle=75)
bubble_mesh = make_mesh('bubble', sphere(1, 16, 10), 'bubble', angle=89)
for k in range(32):
    a, d = rng.uniform(0, math.tau), math.sqrt(rng.uniform(0, 1)) * 0.34
    high = k > 22
    z = 0.8 + (rng.uniform(0.2, 1.2) if high else rng.uniform(0, 0.03))
    place(f'bubble.{k}', bubble_mesh, CAULDRON + pot_base + Vector((d * math.cos(a), d * math.sin(a), z)), (0, 0, 0), rng.uniform(0.03, 0.075) if high else rng.uniform(0.02, 0.055))
point_light('cauldron.brew_light', CAULDRON + pot_base + Vector((0, 0, 1.2)), (0.25, 1.0, 0.2), 0.9)

log = make_mesh('log', rough_up(tube([(-0.42, 0, 0), (-0.1, 0.02, 0.02), (0.42, -0.02, 0)], [0.058, 0.07, 0.055], 9), 0.012, 9), 'bark', angle=60,
                paint=tint((0.008, 0.006, 0.005), (0.07, 0.04, 0.025), 8))
for k in range(5):
    a = k / 5 * math.tau
    place(f'log.{k}', log, CAULDRON + Vector((0.13 * math.cos(a), 0.13 * math.sin(a), 0.08)), (0, -0.36, a + rng.uniform(-0.1, 0.1)), 0.86)


def flame_mesh(name, seed, mat):
    def shape(u, v):
        theta = u * math.tau
        z = v
        radius = 0.18 * (math.sin(v * math.pi) ** 0.7) * (1 - v * 0.55)
        swirl = fbm(math.cos(theta) * 0.9 + seed, math.sin(theta) * 0.9, z * 3 + seed, 2)
        radius *= 1 + swirl * 0.5
        lean = 0.15 * z * z
        return radius * math.cos(theta) + lean * math.cos(seed), radius * math.sin(theta) + lean * math.sin(seed), z
    return make_mesh(name, surface(shape, 16, 14), mat, angle=80)


flames = [flame_mesh(f'flame.{k}', k * 1.7, 'fire') for k in range(4)]
for k in range(10):
    a, d = rng.uniform(0, math.tau), rng.uniform(0.02, 0.34)
    place(f'fire.{k}', flames[k % 4], CAULDRON + Vector((d * math.cos(a), d * math.sin(a), 0.05)), (0, 0, rng.uniform(0, 6)), (rng.uniform(0.7, 1.2), rng.uniform(0.7, 1.2), rng.uniform(0.25, 0.42)))
point_light('cauldron.fire_light', CAULDRON + Vector((0.1, -0.6, 0.22)), (1.0, 0.36, 0.08), 0.4)

# Stones ringing the fire.
pebble = make_mesh('pebble', rough_up(sphere(1, 12, 8), 0.25, 1.4), 'stone', angle=60, paint=stone_paint)
for k in range(14):
    a = k / 14 * math.tau + rng.uniform(-0.05, 0.05)
    place(f'pebble.{k}', pebble, CAULDRON + Vector((0.72 * math.cos(a), 0.72 * math.sin(a), 0.03)), (0, 0, rng.uniform(0, 6)), rng.uniform(0.07, 0.12))


# --- Potion crate ------------------------------------------------------------
CRATE = Vector(ground_at(3.75, -4.7))
wood_paint = tint((0.1, 0.055, 0.03), (0.28, 0.17, 0.09), 3.2)
boards = []
for k in range(5):
    z = 0.03 + k * 0.1
    boards.append(xf(rough_up(surface_grid_box(0.9, 0.018, 0.09, 3), 0.005, 8), (0, -0.33, z)))
    boards.append(xf(rough_up(surface_grid_box(0.9, 0.018, 0.09, 3), 0.005, 8), (0, 0.33, z)))
    boards.append(xf(rough_up(surface_grid_box(0.66, 0.018, 0.09, 3), 0.005, 8), (-0.44, 0, z), (0, 0, math.pi / 2)))
    boards.append(xf(rough_up(surface_grid_box(0.66, 0.018, 0.09, 3), 0.005, 8), (0.44, 0, z), (0, 0, math.pi / 2)))
for x in (-0.44, 0.44):
    for y in (-0.33, 0.33):
        boards.append(xf(box(0.06, 0.06, 0.53), (x, y, 0.02)))
for k in range(3):
    boards.append(xf(surface_grid_box(0.98, 0.21, 0.03, 3), (0, -0.23 + k * 0.23, 0.53)))
boards.append(box(0.88, 0.66, 0.03))
crate_rot = (0.012, -0.01, 0.2)
add('crate', merge(*boards), 'wood', CRATE, crate_rot, angle=25, paint=wood_paint)
crate_matrix = Matrix.LocRotScale(CRATE + Vector((0, 0, 0.56)), Euler(crate_rot), None)


def on_crate(x, y):
    return crate_matrix @ Vector((x, y, 0))


round_flask = [(0.0, 0.0), (0.055, 0.0), (0.09, 0.02), (0.115, 0.075), (0.11, 0.13), (0.075, 0.175), (0.028, 0.205), (0.024, 0.28), (0.032, 0.29), (0.024, 0.3), (0.0, 0.3)]
tall_flask = [(0.0, 0.0), (0.06, 0.0), (0.066, 0.015), (0.066, 0.18), (0.03, 0.235), (0.022, 0.31), (0.03, 0.32), (0.022, 0.33), (0.0, 0.33)]
square_flask = [(0.0, 0.0), (0.095, 0.0), (0.1, 0.01), (0.1, 0.15), (0.03, 0.19), (0.024, 0.25), (0.03, 0.26), (0.0, 0.26)]
potion_kinds = [(round_flask, 48, 'glass_red'), (tall_flask, 32, 'glass_green'), (square_flask, 4, 'glass_purple'), (round_flask, 48, 'glass_green'), (tall_flask, 32, 'glass_purple')]
for k, ((x, y, s), (profile, around, mat)) in enumerate(zip([(-0.28, 0.05, 1.05), (0.02, 0.17, 1.0), (0.3, -0.03, 0.95), (-0.09, -0.18, 0.75), (0.34, 0.2, 0.75)], potion_kinds)):
    loc = on_crate(x, y)
    add(f'potion.{k}', lathe(profile, around), mat, loc, (0, 0, rng.uniform(0, 3)), s, angle=None if around == 4 else 60)
    top = profile[-1][1]
    add(f'potion.{k}.cork', lathe([(0.0, 0), (0.024, 0), (0.03, 0.055), (0.0, 0.055)], 12), 'cork', loc + Vector((0, 0, (top - 0.02) * s)), scale=s, angle=40)


def candle(name, loc, height, radius=0.03, light=0.5):
    drips = [lathe([(0.0, 0), (radius, 0), (radius * 1.03, height * 0.5), (radius * 0.97, height), (radius * 0.55, height * 1.015), (0.0, height * 0.99)], 16)]
    for d in range(6):
        a = rng.uniform(0, math.tau)
        z = rng.uniform(0.25, 0.95) * height
        drips.append(xf(sphere(radius * 0.25, 8, 6), (radius * math.cos(a), radius * math.sin(a), z), scale=(1, 1, rng.uniform(1.8, 3.2))))
    add(name, merge(*drips), 'wax', loc, angle=70)
    add(f'{name}.wick', tube([(0, 0, height * 0.98), (0.002, 0.001, height + radius * 0.5)], radius * 0.05, 5), 'black', loc)
    flame = lathe([(0.0, 0), (radius * 0.33, radius * 0.25), (radius * 0.42, radius * 0.6), (radius * 0.2, radius * 1.15), (0.0, radius * 1.8)], 12)
    add(f'{name}.flame', flame, 'flame', Vector(loc) + Vector((0, 0, height + radius * 0.15)), angle=80)
    point_light(f'{name}.light', Vector(loc) + Vector((0, 0, height + radius * 2.3)), (1.0, 0.55, 0.2), light)


candle('candle.crate', on_crate(-0.05, 0.12), 0.23, 0.035, 0.12)
candle('candle.grave1', ground_at(-1.15, -0.95, 0.0), 0.3, 0.04, 0.14)
candle('candle.grave2', ground_at(-0.85, -1.0, 0.0), 0.2, 0.034, 0.1)
candle('candle.grave3', ground_at(2.05, -0.3, 0.0), 0.26, 0.036, 0.12)


chalice = [(0.0, 0.0), (0.07, 0.0), (0.075, 0.012), (0.02, 0.035), (0.012, 0.1), (0.022, 0.12), (0.012, 0.135), (0.03, 0.15), (0.075, 0.2), (0.085, 0.29),
           (0.078, 0.29), (0.068, 0.205), (0.0, 0.16)]
add('chalice', lathe(chalice, 48), 'gold', on_crate(0.2, -0.2), angle=50)


# --- Showpieces: a crystal ball that refracts the graveyard and focuses light,
# and a garden gazing ball that mirrors the whole scene.
def pedestal(height, top):
    return lathe([(0.0, 0), (top * 1.3, 0), (top * 1.3, 0.07), (top * 0.85, 0.12), (top * 0.5, 0.2), (top * 0.42, height * 0.6), (top * 0.55, height - 0.1),
                  (top, height - 0.05), (top, height), (0.0, height)], 28)


crystal_base = Vector(ground_at(1.45, -4.45, -0.02))
add('crystal.pedestal', pedestal(0.5, 0.36), 'stone', crystal_base, angle=40, paint=stone_paint)
for k in range(3):
    a = k / 3 * math.tau + 0.5
    add(f'crystal.claw.{k}', tube([(0.1 * math.cos(a), 0.1 * math.sin(a), 0.5), (0.18 * math.cos(a), 0.18 * math.sin(a), 0.54), (0.19 * math.cos(a), 0.19 * math.sin(a), 0.6)], [0.014, 0.012, 0.005], 6), 'gold', crystal_base)
add('crystal', sphere(0.27, 96, 64), 'crystal', crystal_base + Vector((0, 0, 0.77)), angle=89)
gazing_base = Vector(ground_at(-3.0, -0.35, -0.02))
add('gazing.pedestal', pedestal(0.86, 0.24), 'stone', gazing_base, angle=40, paint=stone_paint)
add('gazing', sphere(0.29, 96, 64), 'mirror', gazing_base + Vector((0, 0, 1.13)), angle=89)


# --- Hanging lantern, crows, webs --------------------------------------------
def lantern(name, loc, s=1.0, power=0.5):
    loc = Vector(loc)
    cage = []
    for a in range(6):
        angle = a / 6 * math.tau
        cage.append(tube([(0.11 * math.cos(angle), 0.11 * math.sin(angle), 0), (0.13 * math.cos(angle), 0.13 * math.sin(angle), 0.26)], 0.006, 5))
    cage.append(lathe([(0.0, -0.02), (0.14, -0.02), (0.14, 0), (0.0, 0.01)], 6))
    cage.append(xf(lathe([(0.15, 0), (0.15, 0.015), (0.03, 0.12), (0.0, 0.12)], 6), (0, 0, 0.26)))
    ring = [(0.03 * math.cos(a / 12 * math.tau), 0, 0.42 + 0.03 * math.sin(a / 12 * math.tau)) for a in range(13)]
    cage.append(tube(ring, 0.004, 5))
    add(name, merge(*cage), 'iron', loc, scale=s, angle=30)
    candle(f'{name}.candle', loc + Vector((0, 0, 0.002)), 0.09 * s, 0.022 * s, power)


tips = sorted(hero_tips, key=lambda tip: abs(tip[0].x + 2.8) + abs(tip[0].y + 3.6) + max(0, 4.0 - tip[0].z) * 0.6)
lantern_tip = tips[0][0] if tips else Vector((-2.6, -0.2, 5))
hanging_at = Vector((lantern_tip.x, lantern_tip.y, max(3.0, lantern_tip.z - 1.5)))
lantern('lantern', hanging_at, 1.9, 2.4)
for index, (x, y) in enumerate([(gate_center - 1.0, GATE_Y), (gate_center + 1.0, GATE_Y), (-1.05, -2.4), (2.05, -3.3), (-0.95, 3.6), (2.5, 4.0)]):
    if y != GATE_Y:
        place(f'pillar.{index}', post, ground_at(x, y, -0.1))
    lantern(f'lantern.{index}', ground_at(x, y, 1.76), 1.15, 1.5)
add('lantern.chain', tube([hanging_at + Vector((0, 0, 0.8)), lantern_tip], 0.009, 5), 'iron')

crow_mesh = make_mesh('crow', merge(
    xf(sphere(1, 16, 10), (0, 0, 0.14), scale=(0.075, 0.15, 0.095)),
    xf(sphere(0.062, 12, 8), (0, -0.13, 0.22)),
    xf(lathe([(0.0, 0), (0.028, 0), (0.0, 0.1)], 7), (0, -0.18, 0.21), (math.radians(100), 0, 0)),
    xf(tube([(0, 0.1, 0.13), (0, 0.33, 0.04)], [0.05, 0.02], 6), scale=(1.1, 1, 1)),
    xf(sphere(1, 10, 6), (-0.078, 0.03, 0.15), scale=(0.018, 0.12, 0.065)),
    xf(sphere(1, 10, 6), (0.078, 0.03, 0.15), scale=(0.018, 0.12, 0.065))), 'feather', angle=60)
crow_eye = make_mesh('crow_eye', merge(xf(sphere(0.012, 8, 6), (-0.04, -0.16, 0.235)), xf(sphere(0.012, 8, 6), (0.04, -0.16, 0.235))), 'eye', angle=89)
perches = sorted([tip for tip in hero_tips if 3.5 < tip[0].z < 7.8], key=lambda tip: tip[0].x)[::max(1, len(hero_tips) // 7)][:5]
for index, (p, _, _) in enumerate(perches):
    rot = (0, 0, rng.uniform(-0.8, 0.8))
    place(f'crow.{index}', crow_mesh, p + Vector((0, 0, -0.03)), rot, rng.uniform(0.9, 1.25))
    place(f'crow.{index}.eye', crow_eye, p + Vector((0, 0, -0.03)), rot, 1)
for index, (x, y, z, turn) in enumerate([(-3.4, 3.0, 1.16, 0.2)]):
    place(f'crow.grave.{index}', crow_mesh, ground_at(x, y, z - 0.09), (0, 0, turn), 0.9)
    place(f'crow.grave.{index}.eye', crow_eye, ground_at(x, y, z - 0.09), (0, 0, turn), 0.9)


def spider_web(name, center, radius, tilt):
    spokes, threads = 11, []
    angles = [i / spokes * math.tau + rng.uniform(-0.1, 0.1) for i in range(spokes)]
    lengths = [radius * rng.uniform(0.8, 1.2) for _ in range(spokes)]
    for a, length in zip(angles, lengths):
        threads.append(tube([(0, 0, 0), (length * math.cos(a), 0, length * math.sin(a))], 0.0025, 3))
    for ring in range(1, 8):
        t = ring / 8.0
        for i in range(spokes):
            j = (i + 1) % spokes
            a0, a1 = angles[i], angles[j]
            p0 = Vector((lengths[i] * t * math.cos(a0), 0, lengths[i] * t * math.sin(a0)))
            p1 = Vector((lengths[j] * t * math.cos(a1), 0, lengths[j] * t * math.sin(a1)))
            threads.append(tube([p0, (p0 + p1) * 0.5 * 0.93, p1], 0.002, 3))
    add(name, merge(*threads), 'web', center, tilt, angle=89)


spider_web('web.tree', (-4.2, -2.7, 2.1), 0.7, (0.15, 0.1, 0.35))
spider_web('web.gate', (gate_center + 1.5, GATE_Y - 0.04, 1.1), 0.4, (0, 0.1, 0.1))
spider_web('web.grave', (2.75, 3.45, 0.75), 0.33, (0.1, 0, 0.3))
spider_web('web.porch', (HOUSE[0] - 2.0, HOUSE[1] - 4.8, HOUSE[2] + 2.0), 0.55, (0, 0, 0))

spider = merge(xf(sphere(1, 12, 8), (0, 0, 0), scale=(0.03, 0.04, 0.026)), xf(sphere(0.018, 10, 7), (0, -0.04, 0.002)))
for sign in (-1, 1):
    for k in range(4):
        a = -0.75 + k * 0.5
        spider = merge(spider, tube([(0, 0, 0), (sign * 0.055 * math.cos(a), 0.055 * math.sin(a), 0.03), (sign * 0.1 * math.cos(a), 0.1 * math.sin(a), -0.04)], [0.004, 0.003, 0.0015], 4))
add('spider', spider, 'black', (-4.05, -2.75, 2.0), (1.4, 0, 0.3), 1.2, angle=70)


# --- Ghost, witch hat, black cat, bats ---------------------------------------
def ghost_surface(u, v, phase=0.0):
    """Open at the hem, so the two-sided, glowing sheet reads as cloth."""
    theta = u * math.tau
    drop = v
    height = 1.65 * (1 - drop)
    bell = (math.sin(min(1, drop / 0.2) * math.pi / 2) ** 0.6) * (0.28 + 0.2 * drop ** 1.5)
    wave = 1 + 0.2 * math.sin(theta * 7 + drop * 5 + phase) * drop ** 1.6 + 0.08 * math.sin(theta * 3 + 1) * drop
    sway = 0.2 * math.sin(drop * 3.5 + phase) * drop
    hem = -0.14 * drop ** 6 * (1 + math.sin(theta * 7))
    return bell * wave * math.cos(theta) + sway, bell * wave * math.sin(theta), height + hem


def ghost_mesh(name, phase):
    rows, columns = 42, 72
    verts = [Vector(ghost_surface(0, 0, phase))] + [Vector(ghost_surface(i / columns, j / rows, phase)) for j in range(1, rows + 1) for i in range(columns)]
    faces = [(0, 1 + i, 1 + (i + 1) % columns) for i in range(columns)]
    for j in range(rows - 1):
        for i in range(columns):
            a = 1 + j * columns + i
            b = 1 + j * columns + (i + 1) % columns
            faces.append((a, a + columns, b + columns, b))
    return make_mesh(name, (verts, faces), 'ghost', angle=80)


ghost_sheets = [ghost_mesh(f'ghost_sheet.{k}', k * 2.1) for k in range(3)]
ghost_eyes = make_mesh('ghost_eyes', merge(xf(sphere(0.055, 12, 8), (-0.13, -0.27, 1.32), scale=(1, 0.5, 1.45)), xf(sphere(0.055, 12, 8), (0.1, -0.29, 1.32), scale=(1, 0.5, 1.45)),
                                           xf(sphere(0.06, 12, 8), (-0.015, -0.33, 1.1), scale=(1, 0.45, 1.3))), 'black', angle=80)
# x, y, height above the ground or water, size, heading.
for index, (x, y, lift, size, turn) in enumerate([(0.7, 2.0, 0.55, 1.0, -0.3), (-2.05, 2.6, 0.5, 0.72, 0.25), (-4.2, 5.2, 0.9, 0.85, -0.2), (3.0, 5.6, 0.7, 0.68, 0.3),
                                                  (-0.75, -1.6, 0.85, 0.42, -0.15), (6.6, 0.0, 2.6, 0.6, 0.5), (-1.9, 9.4, 2.4, 0.6, 0.15), (2.6, 10.2, 2.1, 0.5, -0.35),
                                                  (-3.4, 0.8, 2.2, 0.5, 0.4)]):
    loc = surface_at(x, y, lift)
    rot = (0.03, rng.uniform(-0.06, 0.06), turn)
    place(f'ghost.{index}', ghost_sheets[index % 3], loc, rot, size)
    place(f'ghost.{index}.eyes', ghost_eyes, loc, rot, size)

hat_path = [(0, 0, 0.02), (0.0, 0, 0.15), (0.015, 0, 0.3), (0.05, 0.0, 0.42), (0.1, 0.0, 0.5), (0.18, 0.01, 0.53), (0.26, 0.02, 0.48)]
hat_radii = [0.13, 0.115, 0.09, 0.066, 0.045, 0.027, 0.004]
hat_parts = [tube(hat_path, hat_radii, 24),
             lathe([(0.0, -0.006), (0.27, -0.006), (0.29, 0.005), (0.28, 0.012), (0.12, 0.02), (0.0, 0.02)], 40)]
hat_loc = ground_at(-1.0, -0.6, 1.1)
add('hat', merge(*hat_parts), 'fabric', hat_loc, (0.06, 0.05, 0.6), 1.2, angle=70)
add('hat.band', lathe([(0.135, 0), (0.14, 0.002), (0.128, 0.06), (0.12, 0.06)], 30), 'black', hat_loc, (0.06, 0.05, 0.6), 1.2)
add('hat.buckle', merge(xf(box(0.07, 0.012, 0.012), (0, 0, 0.0)), xf(box(0.07, 0.012, 0.012), (0, 0, 0.055)),
                        xf(box(0.012, 0.012, 0.06), (-0.03, 0, 0)), xf(box(0.012, 0.012, 0.06), (0.03, 0, 0))),
    'gold', Vector(hat_loc) + Vector((-0.09, -0.13, 0)), (0.06, 0.05, 0.6), 1.2, angle=None)

cat = merge(
    xf(sphere(1, 18, 12), (0, 0.04, 0.17), (0.25, 0, 0), (0.1, 0.13, 0.18)),
    xf(sphere(1, 18, 12), (0, -0.05, 0.05), scale=(0.11, 0.09, 0.08)),
    xf(sphere(1, 18, 12), (0, -0.02, 0.37), scale=(0.095, 0.085, 0.085)),
    xf(lathe([(0.0, 0), (0.038, 0), (0.0, 0.1)], 6), (-0.055, -0.01, 0.41), (0, -0.22, 0)),
    xf(lathe([(0.0, 0), (0.038, 0), (0.0, 0.1)], 6), (0.055, -0.01, 0.41), (0, 0.22, 0)),
    tube([(-0.05, -0.08, 0.2), (-0.055, -0.11, 0.08), (-0.055, -0.13, 0.0)], [0.028, 0.024, 0.026], 8),
    tube([(0.05, -0.08, 0.2), (0.055, -0.11, 0.08), (0.055, -0.13, 0.0)], [0.028, 0.024, 0.026], 8),
    tube([(0, 0.14, 0.05), (0.13, 0.16, 0.03), (0.21, 0.08, 0.1), (0.22, 0.04, 0.23), (0.27, 0.05, 0.3)], [0.03, 0.026, 0.022, 0.02, 0.012], 8))
# The perch is the sloped slab in front of the second grave.
cat_loc = ground_at(1.75, -1.25, 0.33)
add('perch', rough_up(xf(surface_grid_box(0.85, 0.6, 0.34, 8), (0, 0, 0)), 0.02, 4), 'stone', ground_at(1.75, -1.25, -0.02), (0, 0.02, 0.2), angle=60, paint=grave_paint)
add('cat.body', cat, 'black', cat_loc, (0, 0, 0.45), 1.05, angle=70)
add('cat.eyes', merge(xf(sphere(0.016, 10, 7), (-0.036, -0.09, 0.385), scale=(1.25, 0.5, 1)), xf(sphere(0.016, 10, 7), (0.036, -0.09, 0.385), scale=(1.25, 0.5, 1))),
    'eye', cat_loc, (0, 0, 0.45), 1.05, angle=89)


def bat_mesh():
    points, faces = [], []
    wing_outline = [(0, 0.1), (0.15, 0.2), (0.45, 0.42), (0.85, 0.34), (1.2, 0.08), (0.95, 0.08), (0.8, -0.12), (0.6, 0.03), (0.42, -0.2), (0.22, -0.03), (0.0, -0.2)]
    for sign in (-1, 1):
        start = len(points)
        for i, (x, y) in enumerate(wing_outline):
            points.append(Vector((sign * x, y * 0.5, abs(x) ** 1.5 * 0.2)))
        indices = list(range(start, start + len(wing_outline)))
        faces.append(tuple(indices if sign > 0 else indices[::-1]))
    return merge((points, faces), xf(sphere(1, 12, 8), (0, 0, 0), scale=(0.1, 0.22, 0.08)), xf(sphere(0.09, 10, 7), (0, -0.21, 0.02)),
                 xf(lathe([(0.0, 0), (0.035, 0), (0.0, 0.1)], 5), (-0.05, -0.21, 0.08)), xf(lathe([(0.0, 0), (0.035, 0), (0.0, 0.1)], 5), (0.05, -0.21, 0.08)))


bat = make_mesh('bat', bat_mesh(), 'black', angle=None)
for index, (x, y, z, size, turn, roll) in enumerate([(8.2, 18, 9.6, 1.0, 0.4, 0.3), (10.6, 22, 11.8, 1.2, -0.5, -0.3), (5.3, 15, 10.2, 0.75, 0.9, 0.35), (15.6, 28, 11.0, 1.4, -0.8, 0.2),
                                                       (12.5, 30, 16.0, 1.0, 0.2, -0.3), (1.0, 11, 9.4, 0.55, 1.8, 0.2), (-2.3, 9, 7.8, 0.5, -2.2, -0.4), (6.5, 12, 6.8, 0.5, 1.1, 0.5)]):
    place(f'bat.{index}', bat, (x, y, z), (-0.2, roll, turn), size)


# --- Grass, leaves, mushrooms ------------------------------------------------
tufts = []
for variant in range(3):
    blades = []
    for k in range(9):
        a = rng.uniform(0, math.tau)
        d = rng.uniform(0, 0.05)
        h = rng.uniform(0.11, 0.26)
        bend = rng.uniform(0.02, 0.1)
        base = Vector((d * math.cos(a), d * math.sin(a), 0))
        out = Vector((math.cos(a), math.sin(a), 0))
        side = Vector((-math.sin(a), math.cos(a), 0)) * 0.007
        mid = base + out * bend * 0.3 + Vector((0, 0, h * 0.6))
        tip = base + out * bend + Vector((0, 0, h))
        blades.append(([base - side, base + side, mid + side * 0.6, mid - side * 0.6, tip], [(0, 1, 2, 3), (3, 2, 4)]))
    tufts.append(make_mesh(f'tuft.{variant}', merge(*blades), 'grass', angle=80))
for index in range(2200):
    x, y = rng.uniform(-13, 14), rng.uniform(-7, 12)
    if abs(x - path_x(y)) < 0.7 and y < 11:
        continue
    if any(puddle_distance(x, y, puddle) < 1.05 for puddle in PUDDLES):
        continue
    if fbm(x * 0.5, y * 0.5, 3.0) < -0.12 or y > 9 and abs(x) < 7:
        continue
    place(f'tuft.{index}', tufts[index % 3], ground_at(x, y, -0.01), (rng.uniform(-0.1, 0.1), rng.uniform(-0.1, 0.1), rng.uniform(0, 6)), rng.uniform(0.7, 1.7))

leaf_outline = [(0, -0.5), (0.2, -0.32), (0.28, -0.05), (0.42, 0.1), (0.24, 0.16), (0.2, 0.36), (0, 0.5), (-0.2, 0.36), (-0.24, 0.16), (-0.42, 0.1), (-0.28, -0.05), (-0.2, -0.32)]
leaves = [make_mesh(f'leaf.{name}', ([Vector((x, y, 0.09 * math.sin(y * 3 + k))) for x, y in leaf_outline], [tuple(range(len(leaf_outline)))]), f'leaf_{name}', angle=None)
          for k, name in enumerate('abc')]
carpets = []
for k, name in enumerate(('leaf_a', 'leaf_b', 'leaf_c')):
    parts = []
    for _ in range(46):
        center = Vector((rng.gauss(0, 0.55), rng.gauss(0, 0.55), rng.uniform(0.005, 0.05)))
        size = rng.uniform(0.12, 0.25)
        leaf = ([Vector((x, y, 0.06 * math.sin(y * 4))) for x, y in MAPLE], [tuple(range(len(MAPLE)))])
        parts.append(xf(leaf, center, (rng.uniform(-0.3, 0.3), rng.uniform(-0.3, 0.3), rng.uniform(0, math.tau)), size))
    carpets.append(make_mesh(f'carpet.{name}', merge(*parts), name, angle=None))
for index in range(1000):
    x, y = rng.uniform(-9, 8), rng.uniform(-9, 12)
    # Keep the path and the water mostly clear, as if swept.
    if abs(x - path_x(y)) < 0.75 and rng.random() < 0.85 or any(puddle_distance(x, y, puddle) < 1.1 for puddle in PUDDLES):
        continue
    place(f'carpet.{index}', carpets[index % 3], ground_at(x, y, 0.0), (0, 0, rng.uniform(0, 6)), rng.uniform(0.8, 1.3))
for index in range(70):
    a, d = rng.uniform(0, math.tau), rng.uniform(0.2, 4.5)
    place(f'crown_fall.{index}', clusters[index % 6], ground_at(-3.2 + d * math.cos(a) * 1.2, -7.2 + abs(d * math.sin(a)) * 0.5, 0.08), (0.0, 0.0, rng.uniform(0, 6)), (0.9, 0.9, 0.12))


# Leaves still falling through the air, thickest under the big crown.
drifting = [make_mesh(f'crown_drift.{name}', merge(leaf_part((0, 0, 0), 0.2)), name, angle=None) for name in ('leaf_a', 'leaf_b', 'leaf_c')]
for index in range(240):
    near = index < 150
    x, y = (rng.gauss(-2.5, 2.4), rng.uniform(-6.5, -1)) if near else (rng.uniform(-8, 6), rng.uniform(-2, 8))
    z = surface_z(x, y) + rng.uniform(0.25, 4.2)
    if x > 2.5 and z > 2.6:  # Keep the moon clear.
        continue
    place(f'crown_drift.{index}', drifting[index % 3], (x, y, z), (rng.uniform(0, 6), rng.uniform(0, 6), rng.uniform(0, 6)), rng.uniform(0.8, 1.5))


# Rock ledge along the near left, under the pumpkins.
ledge = make_mesh('ledge', rough_up(sphere(1, 14, 9), 0.22, 1.1), 'stone', angle=55, paint=tint((0.3, 0.27, 0.24), (0.62, 0.55, 0.47), 1.3))
for index, (x, y, size) in enumerate([(-3.7, -7.0, 0.5), (-2.8, -7.2, 0.45), (-1.9, -7.1, 0.5), (-1.0, -6.9, 0.38), (-0.25, -6.75, 0.3), (-4.6, -6.3, 0.6)]):
    place(f'ledge.{index}', ledge, ground_at(x, y, size * 0.2), (0, 0, rng.uniform(0, 6)), (size * 1.2, size * 0.8, size * 0.7))


# Stairs up the rise to the porch.
step = make_mesh('step', rough_up(surface_grid_box(2.2, 0.48, 0.2, 5), 0.012, 4), 'stone', angle=45, paint=stone_paint)
for index in range(11):
    y = 9.0 + index * 0.42
    place(f'step.{index}', step, ground_at(path_x(9.2), y, -0.09), (0, 0, 0))


# Village lights across the lake.
cottage = make_mesh('cottage', merge(box(1.0, 0.8, 0.6), xf(lathe([(0.82, 0), (0.0, 0.55)], 4), (0, 0, 0.6), (0, 0, math.pi / 4))), 'black', angle=None)
lit = make_mesh('cottage_window', merge(xf(box(0.22, 0.05, 0.28), (-0.2, -0.42, 0.15)), xf(box(0.22, 0.05, 0.28), (0.24, -0.42, 0.15))), 'window', angle=None)
for index in range(46):
    x, y = rng.uniform(22, 62), rng.uniform(66, 72)
    loc = (x, y, -4.4 + rng.uniform(0, 2.2))
    size = rng.uniform(1.1, 1.8)
    place(f'cottage.{index}', cottage, loc, (0, 0, rng.uniform(-0.3, 0.3)), size)
    place(f'cottage.{index}.lit', lit, loc, (0, 0, 0), size)


mushroom_stem = make_mesh('mushroom_stem', lathe([(0.0, 0), (0.05, 0), (0.038, 0.1), (0.03, 0.2), (0.0, 0.22)], 12), 'bone', angle=60)
mushroom_cap = make_mesh('mushroom_cap', lathe([(0.0, 0.17), (0.16, 0.14), (0.18, 0.17), (0.12, 0.26), (0.0, 0.3)], 20), 'mushroom', angle=60)
for index, (x, y) in enumerate([(-4.7, -0.9), (-4.5, -0.55), (-5.0, -0.45), (-3.6, -0.3), (1.2, -3.1), (1.45, -2.75), (5.4, 1.5), (-2.1, -1.1), (-2.35, -0.8)]):
    s, turn = rng.uniform(0.55, 1.2), rng.uniform(0, 6)
    tilt = rng.uniform(-0.12, 0.12)
    place(f'mushroom.{index}', mushroom_stem, ground_at(x, y), (tilt, -tilt, turn), s)
    place(f'mushroom_cap.{index}', mushroom_cap, ground_at(x, y), (tilt, -tilt, turn), s)


# --- Moon and moonlight ------------------------------------------------------
def moon_image(size=512):
    image = bpy.data.images.new('moon', size, size // 2, alpha=False)
    craters = [(rng.uniform(0, 1), rng.uniform(0.15, 0.85), rng.uniform(0.015, 0.09)) for _ in range(40)]
    pixels = [0.0] * (size * (size // 2) * 4)
    for row in range(size // 2):
        v = (row + 0.5) / (size // 2)
        elevation = (v - 0.5) * math.pi
        for col in range(size):
            u = (col + 0.5) / size
            theta = u * math.tau
            n = Vector((math.cos(elevation) * math.cos(theta), math.cos(elevation) * math.sin(theta), math.sin(elevation)))
            mare = 0.72 + 0.5 * fbm(n.x * 2.2, n.y * 2.2, n.z * 2.2, 4) + 0.1 * fbm(n.x * 12, n.y * 12, n.z * 12, 2)
            for cu, cv, radius in craters:
                d_u = min(abs(u - cu), 1 - abs(u - cu)) * 2 * math.cos(elevation)
                d = math.hypot(d_u, v - cv)
                if d < radius:
                    mare *= 0.8 + 0.2 * (d / radius) ** 2
                elif d < radius * 1.2:
                    mare *= 1.08
            offset = (row * size + col) * 4
            mare = max(0.05, min(1, mare))
            pixels[offset:offset + 4] = [mare, mare * 0.82, mare * 0.5, 1]
    image.pixels = pixels
    image.pack()
    return image


moon = material('moon', (0, 0, 0), 1, emit=(1, 1, 1), strength=7)
nodes = moon.node_tree.nodes
texture = nodes.new('ShaderNodeTexImage')
texture.image = moon_image()
moon.node_tree.links.new(texture.outputs['Color'], nodes['Principled BSDF'].inputs['Emission Color'])
M['moon'] = moon
around, along = 64, 32
moon_verts, moon_uvs, moon_faces = [], [], []
for j in range(along + 1):
    for i in range(around + 1):
        theta, elevation = i / around * math.tau, (j / along - 0.5) * math.pi
        moon_verts.append((math.cos(elevation) * math.cos(theta), math.cos(elevation) * math.sin(theta), math.sin(elevation)))
        moon_uvs.append((i / around, j / along))
for j in range(along):
    for i in range(around):
        a = j * (around + 1) + i
        moon_faces.append((a, a + 1, a + around + 2, a + around + 1))
moon_mesh = make_mesh('moon', (moon_verts, moon_faces), 'moon', angle=89)
uv_layer = moon_mesh.uv_layers.new(name='UVMap')
for polygon in moon_mesh.polygons:
    for loop_index in polygon.loop_indices:
        uv_layer.data[loop_index].uv = moon_uvs[moon_mesh.loops[loop_index].vertex_index]
MOON = Vector((46, 88, 33))
place('moon', moon_mesh, MOON, (0.5, 0, 2.5), 8.5)

moonlight = bpy.data.lights.new('moonlight', 'SUN')
moonlight.color = (0.5, 0.48, 1.0)
moonlight.energy = 1.7
sun = place('moonlight', moonlight, MOON)
# A sun light shines along its local -Z: aim it from the moon toward the graveyard.
sun.rotation_euler = (MOON - Vector((0, 0, 0))).to_track_quat('Z', 'Y').to_euler()

def emission_material(name, image):
    result = material(name, (0, 0, 0), 1, emit=(1, 1, 1), strength=1)
    texture = result.node_tree.nodes.new('ShaderNodeTexImage')
    texture.image = image
    result.node_tree.links.new(texture.outputs['Color'], result.node_tree.nodes['Principled BSDF'].inputs['Emission Color'])
    M[name] = result


def set_uvs(mesh, uvs):
    layer = mesh.uv_layers.new(name='UVMap')
    for polygon in mesh.polygons:
        for loop_index in polygon.loop_indices:
            layer.data[loop_index].uv = uvs[mesh.loops[loop_index].vertex_index]


# Mist: upright cards whose texture is used as an alpha map by the example.
def mist_image(size=512):
    noise_field = tile_noise(size, 1.3, 21)
    axis = (np.arange(size) + 0.5) / size * 2 - 1
    fade = np.clip(1 - axis[:, None] ** 2, 0, 1) * np.clip(1 - axis[None, :] ** 4, 0, 1)
    alpha = np.clip((noise_field - 0.28) * 2.4, 0, 1) * fade
    image = pack_image('mist', np.dstack((alpha, alpha, alpha)), 'Non-Color')
    return image


emission_material('mist', mist_image())
card = make_mesh('mist', ([(-0.5, 0, 0), (0.5, 0, 0), (0.5, 0, 1), (-0.5, 0, 1)], [(0, 1, 2, 3)]), 'mist', angle=None)
set_uvs(card, [(0, 0), (1, 0), (1, 1), (0, 1)])
M['mist'].use_backface_culling = False
for index, (x, y, z, w, h) in enumerate([(-8, 10.5, 0.2, 18, 2.2), (50, 62, -4.5, 90, 6), (-22, 40, 2, 70, 7)]):
    place(f'mist.{index}', card, (x, y, z), (0, 0, 0), (w, 1, h))

# The cold sky fill from behind the camera lifts the faces the moon leaves in shadow.
sky_fill = bpy.data.lights.new('sky_fill', 'SUN')
sky_fill.color = (0.42, 0.34, 1.0)
sky_fill.energy = 0.42
place('sky_fill', sky_fill, (0, -30, 20)).rotation_euler = Vector((-3, -20, 14)).to_track_quat('Z', 'Y').to_euler()

M['star'] = material('star', (0, 0, 0), 1, emit=(0.85, 0.9, 1.0), strength=5)
star = make_mesh('star', xf(sphere(1, 6, 4)), 'star', angle=None)
for index in range(160):
    x, z = rng.uniform(-110, 110), rng.uniform(30, 75)
    place(f'star.{index}', star, (x, 150, z), (0, 0, 0), 0.07 + 0.2 * rng.random() ** 5)

bpy.context.view_layer.update()
bpy.ops.export_scene.gltf(
    filepath=os.path.abspath(OUTPUT),
    export_format='GLB',
    export_yup=True,
    export_apply=True,
    export_lights=True,
    export_cameras=False,
    export_vertex_color='ACTIVE',
    export_import_convert_lighting_mode='RAW',
    export_image_format='JPEG',
    export_image_quality=85,
)
triangles = sum(sum(len(p.vertices) - 2 for p in mesh.polygons) for mesh in bpy.data.meshes)
print(f'HALLOWEEN objects={len(bpy.data.objects)} meshes={len(bpy.data.meshes)} unique_tris={triangles} '
      f'size_mb={os.path.getsize(OUTPUT) / 1e6:.2f}')

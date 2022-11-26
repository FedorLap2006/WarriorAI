import math
import PIL.Image
from PIL.Image import Image
from . import protocol


def print_chunk(tu):
    print([c.chunk for c in tu.chunks])
    for c in tu.chunks:
        if c.is_update:
            continue
        print(c.chunk_id)
        c.altitudes
        c.print()
        print("======================================")


alt_lookup = [
    -115,
    -100,
    -50,
    -20,
    -5,
    -2,
    -1,
    0,
    1,
    2,
    5,
    20,
    50,
    100,
    115,
]


def resolve_altitude_color(alt) -> tuple[int, int, int]:
    # print(alt)
    if alt > 128:
        return (0, alt, 0)
    else:
        return (0, 0, alt + 128)



def image_coords(img: Image, x: int, y: int) -> tuple[int, int]:
    width, height = img.size

    return width - x - 1, height - y - 1

def draw_chunk(img: Image, chunk: protocol.Chunk):
    for i in range(protocol.CHUNK_SIZE):
        for j in range(protocol.CHUNK_SIZE):
            chunk_x, chunk_y = chunk.chunk_id
            alt = chunk.altitudes[j][i]
            img.putpixel(
                (chunk_x * protocol.CHUNK_SIZE + j, chunk_y * protocol.CHUNK_SIZE + i),
                resolve_altitude_color(alt),
            )


def draw_world_border(img: Image, world_radius: float):
    for i in range(360):
        img.putpixel(
            tuple(
                protocol.TerrainCoords.from_real(
                    protocol.Coords(
                        math.cos(math.radians(i)) * world_radius,
                        math.sin(math.radians(i)) * world_radius,
                    )
                )
            ),
            (255, 0, 0),
        )

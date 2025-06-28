import click
import os
import requests
import time
from xml.dom import minidom
from pathlib import Path
import pdb
import math
import json


def download_metadata(fmt,photo_id, output_dir):
    path = output_dir / f"{photo_id}.{fmt}"
    if path.exists():
        print(f"{fmt} file already exists: {path}")
        with open(path, 'r', encoding='utf-8') as f:
            data = f.read()
    else:
        url = f"http://www.gigapan.com/gigapans/{photo_id}.{fmt}"
        try:
            print(f"{url=}")
            response = requests.get(url)
            data = response.content
            path.write_bytes(data)
            print(f"{fmt} saved to: {path}")
        except Exception as e:
            print(f"Failed to download {fmt}: {e}")
            return None

    if fmt=='json':
        data = json.loads(data)
        data=data['gigapan']
    return data

def parse_kml(kml_path):
    dom = minidom.parse(str(kml_path))
    width = int(dom.getElementsByTagName("maxWidth")[0].firstChild.data)
    height = int(dom.getElementsByTagName("maxHeight")[0].firstChild.data)
    tile_width = int(dom.getElementsByTagName("tileSize")[0].firstChild.data)
    tile_height = int(dom.getElementsByTagName("tileSize")[0].firstChild.data)
    return width, height, tile_width, tile_height

def is_valid_jpeg(data):
    return data.startswith(b'\xff\xd8') and data.endswith(b'\xff\xd9')

def calculate_max_level(pano_width, pano_height, tile_size=256):
    """ I don't think this will actually work """
    tiles_x = pano_width / tile_size
    tiles_y = pano_height / tile_size
    level_x = math.ceil(math.log2(tiles_x))
    level_y = math.ceil(math.log2(tiles_y))
    return max(level_x, level_y)


def get_tile_dimensions(pano_width, pano_height, level,  max_level, tile_size=256):
    """
    Compute number of tiles in x and y directions at a specific quadtree zoom level.
    """
    #max_level=calculate_max_level(pano_width,pano_height, tile_size)
    
    scale = 2 ** (max_level - level)

    level_width = pano_width / scale
    level_height = pano_height / scale

    tiles_x = math.ceil(level_width / tile_size)
    tiles_y = math.ceil(level_height / tile_size)
    print(f'{pano_width=}, {pano_height=}, {level=}, {max_level=} {level_width=} {level_height=} {tiles_x=} {tiles_y=}')

    return tiles_x, tiles_y


def download_tile(photo_id, level, row, col, output_dir):
    tile_url = f"http://www.gigapan.com/get_ge_tile/{photo_id}/{level}/{row}/{col}"
    tile_path = Path(output_dir) / f"{level}/{row}/{col}.jpg"
    tile_path.parent.mkdir(parents=True, exist_ok=True)

    if tile_path.exists():
        print(f"Tile already exists: {tile_path}")
        return tile_path

    try:
        print(f"Downloading tile: {tile_url} {output_dir}")
        response = requests.get(tile_url, timeout=40)
        content = response.content

        if is_valid_jpeg(content) and len(content) > 1000:  # Basic size sanity check
            tile_path.parent.mkdir(parents=True, exist_ok=True)
            with open(tile_path, 'wb') as f:
                f.write(content)
        else:
            raise Exception(f"Invalid or too small JPEG file {tile_path}.")
    except Exception as e:
        print(f"Failed to download {tile_url}: {e}")
        missing_path = Path(output_dir) / "missing_tiles.txt"
        with open(missing_path, 'a') as f:
            f.write(f"{level}/{row}/{col}.jpg\n")

def download_all_tiles(photo_id, output_dir, level=None):
    kml_path = download_metadata('kml',  photo_id, output_dir)
    json_data = download_metadata('json',photo_id, output_dir)

    if level is None:
        print('fetching all tiles')
        level=json_data['levels']-1
        for level in range(level+1):
            print(f'{level}')
            cols,rows = get_tile_dimensions(json_data['width'],json_data['height'],level,json_data['levels']-1)
            for row in range(rows):
                for col in range(cols):
                    download_tile(photo_id, level, row, col,  output_dir)
        return

    if (level > json_data['levels']):
        level=json_data['levels']-1
        print(f'Passed level higher than this pano has, so level reset to {level}')
    
    cols,rows = get_tile_dimensions(json_data['width'],json_data['height'],level,json_data['levels']-1)
    for row in range(rows):
        for col in range(cols):
            download_tile(photo_id, level, row, col,  output_dir)

@click.command()
@click.argument('photo_id', type=int)
@click.argument('zoom_level', required=False, type=int)
@click.option('-o', '--output', default='tiles', help='Output directory')

def main(photo_id, zoom_level, output):

    if output=='tiles':
        output=str(photo_id)

    output_dir = Path(output)

    output_dir.mkdir(parents=True, exist_ok=True)

    download_all_tiles(photo_id, output_dir, zoom_level)


main()


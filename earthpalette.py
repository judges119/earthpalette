import colorgram
import numpy as np
import os
from osgeo import ogr, gdal, osr
from PIL import Image, ImageEnhance
import pytumblr
import random
from reportlab.graphics import renderPM
from svglib.svglib import svg2rlg
import urllib.request

sea_shape_file = r"./world_seas/World_Seas.shp"

x_min = 0
y_min = 0
step = 1
resolution = 1080

# Open the seas shapefile
shp_driver = ogr.GetDriverByName('ESRI Shapefile')
dataSource = shp_driver.Open(sea_shape_file, 0)
if dataSource is None:
    print('Could not open %s' % sea_shape_file)
    exit(2)
layer = dataSource.GetLayer()

# Prep the TIFF driver
image_type = 'GTiff'
tiff_driver = gdal.GetDriverByName(image_type)

#
# Find a random patch of the world, then check if it's got too much sea/ocean.
#
tooMuchWater = True
while tooMuchWater:
    # Random coords and size, we'll use these later
    x_min = random.uniform(-125, 151)
    y_min = random.uniform(-36, 80)
    step = random.uniform(0, 5)
    # Create a new raster from a small square in the seas shapefile
    new_raster = tiff_driver.Create('world_mask.tif', resolution, resolution, 1, gdal.GDT_Byte)
    new_raster.SetGeoTransform((x_min, ((step * 360) / 360) / resolution, 0, y_min, 0, ((step * 180) / 180) / resolution))
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(4326)
    new_raster.SetProjection(srs.ExportToWkt())
    band = new_raster.GetRasterBand(1)
    no_data_value = 0
    band.SetNoDataValue(no_data_value)
    band.FlushCache()
    gdal.RasterizeLayer(new_raster, [1], layer)
    # Check if there is more than 50% sea/ocean pixels in the image.
    raster_array = new_raster.ReadAsArray()
    full_size = raster_array.size
    small_size = raster_array[np.where(raster_array == 255)].size
    if small_size / full_size > 0.5:
        # If too much water, repeat process
        print("too much water")
        print(small_size / full_size)
        new_raster = None
        tiff_driver.Delete('world_mask.tif')
    else:
        # If enough land, continue.
        print("water ratio at or below 0.5")
        print(small_size / full_size)
        tooMuchWater = False

# Make a WMS request for that segment of the globe from a 2020 cloudless Sentinel 2 mosaic
urllib.request.urlretrieve("https://tiles.maps.eox.at/wms?service=wms&request=GetMap&version=1.1.1&layers=s2cloudless-2020&srs=EPSG:4326&bbox=" + str(x_min) + "," + str(y_min) + "," + str(x_min + step) + "," + str(y_min + step) + "&styles=&width=" + str(resolution) + "&height=" + str(resolution) + "&format=image%2Fpng", "world.png")

# Increase the contrast by a 1.25 factor
im = Image.open("world.png")
enhancer = ImageEnhance.Brightness(im)
factor = 1.25 #brightens the image
im_output = enhancer.enhance(factor)
im_output.save('world-bright.png')

# Extract the 6 colour palette
colours = colorgram.extract('./world-bright.png', 6)

# Generate an SVG showing the palette
svg = '<svg width="585" height="100">'
l = 0
for colour in colours:
    svg += '<rect x="' + str(l) + '" y="0" width="100" height="100" style="fill:' + ('#%02x%02x%02x' % colour.rgb) + ';stroke-width:3;stroke:rgb(0,0,0)" />'
    l += 97
svg += '</svg>'
with open('world_colour.svg', 'w') as f:
    f.write(svg)
# Change the SVG to a PNG
drawing = svg2rlg('world_colour.svg')
renderPM.drawToFile(drawing, 'world_colour.png', fmt='PNG')

# Post to Tumblr
client = pytumblr.TumblrRestClient(
    os.environ.get('CONSUMER_KEY'),
    os.environ.get('CONSUMER_SECRET'),
    os.environ.get('OAUTH_TOKEN'),
    os.environ.get('OAUTH_SECRET')
)
client.create_photo('earthpalettes', state="published", tags=["palette", "sentinel"], format="markdown",
                    data=["./world.png", "./world_colour.png"],
                    caption=
'''
## Sentinel 2 Colour Palette

Location between: %g, %g and %g, %g in WGS84 coordinates (EPSG:4326).

This image is from a mosaic of Sentinel-2 images taken in 2020 with the clouds removed, provided by EOX through their [Sentinel-2 Cloudless](https://s2maps.eu/) service.
''' % (y_min, x_min, y_min + step, x_min + step))
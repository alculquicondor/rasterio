import logging
import os.path
import sys

import click

import rasterio

from rasterio.five import zip_longest
from rasterio.rio.cli import cli


PHOTOMETRIC_CHOICES = [val.lower() for val in [
    'MINISBLACK',
    'MINISWHITE',
    'RGB',
    'CMYK',
    'YCBCR',
    'CIELAB',
    'ICCLAB',
    'ITULAB']]


# Stack command.
@cli.command(short_help="Stack a number of bands into a multiband dataset.")
@click.argument('input', nargs=-1,
                type=click.Path(exists=True, resolve_path=True), required=True)
@click.option('--bidx', multiple=True,
              help="Indexes of input file bands.")
@click.option('--photometric', default=None,
              type=click.Choice(PHOTOMETRIC_CHOICES),
              help="Photometric interpretation")
@click.option('-o','--output',
              type=click.Path(exists=False, resolve_path=True), required=True,
              help="Path to output file.")
@click.option('-f', '--format', '--driver', default='GTiff',
              help="Output format driver")
@click.pass_context
def stack(ctx, input, bidx, photometric, output, driver):
    """Stack a number of bands from one or more input files into a
    multiband dataset.

    Input datasets must be of a kind: same data type, dimensions, etc. The
    output is cloned from the first input.

    By default, rio-stack will take all bands from each input and write them
    in same order to the output. Optionally, bands for each input may be
    specified using a simple syntax:

      --bidx N takes the Nth band from the input (first band is 1).

      --bidx M,N,0 takes bands M, N, and O.

      --bidx M..O takes bands M-O, inclusive.

      --bidx ..N takes all bands up to and including N.

      --bidx N.. takes all bands from N to the end.

    Examples, using the Rasterio testing dataset, which produce a copy.

      rio stack RGB.byte.tif -o stacked.tif

      rio stack RGB.byte.tif --bidx 1,2,3 -o stacked.tif

      rio stack RGB.byte.tif --bidx 1..3 -o stacked.tif

      rio stack RGB.byte.tif --bidx ..2 RGB.byte.tif --bidx 3.. -o stacked.tif

    """
    import numpy as np

    verbosity = (ctx.obj and ctx.obj.get('verbosity')) or 2
    logger = logging.getLogger('rio')
    try:
        with rasterio.drivers(CPL_DEBUG=verbosity>2):
            output_count = 0
            indexes = []
            for path, item in zip_longest(input, bidx, fillvalue=None):
                with rasterio.open(path) as src:
                    src_indexes = src.indexes
                if item is None:
                    indexes.append(src_indexes)
                    output_count += len(src_indexes)
                elif '..' in item:
                    start, stop = map(
                        lambda x: int(x) if x else None, item.split('..'))
                    if start is None:
                        start = 1
                    indexes.append(src_indexes[slice(start-1, stop)])
                    output_count += len(src_indexes[slice(start-1, stop)])
                else:
                    parts = list(map(int, item.split(',')))
                    if len(parts) == 1:
                        indexes.append(parts[0])
                        output_count += 1
                    else:
                        parts = list(parts)
                        indexes.append(parts)
                        output_count += len(parts)

            with rasterio.open(input[0]) as first:
                kwargs = first.meta
                kwargs['transform'] = kwargs.pop('affine')

            kwargs.update(
                driver=driver,
                count=output_count)

            if photometric:
                kwargs['photometric'] = photometric

            with rasterio.open(output, 'w', **kwargs) as dst:
                dst_idx = 1
                for path, index in zip(input, indexes):
                    with rasterio.open(path) as src:
                        if isinstance(index, int):
                            data = src.read(index)
                            dst.write(data, dst_idx)
                            dst_idx += 1
                        elif isinstance(index, list):
                            data = src.read(index)
                            dst.write(data, range(dst_idx, dst_idx+len(index)))
                            dst_idx += len(index)

        sys.exit(0)
    except Exception:
        logger.exception("Failed. Exception caught")
        sys.exit(1)

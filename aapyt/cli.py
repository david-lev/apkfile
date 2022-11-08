import os
import click
from aapyt import get_apk_info


@click.command()
@click.argument('filename')
def main(filename):
    info_dict = get_apk_info(os.path.expanduser(filename), as_dict=True)
    output = 'AAPYT - Android APK Information extractor\n\n'
    for key, value in info_dict.items():
        output += f'{key.replace("_", " ").title()}: {value}\n'

    click.echo(output)

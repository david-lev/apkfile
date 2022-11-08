import click
from aapyt import get_apk_info
from json import dumps


@click.command()
@click.argument('apk-path', type=click.Path(exists=True), required=True)
@click.option('--aapt', default=None, help='Path to aapt binary', type=click.Path(exists=True))
@click.option('--json', 'as_json', is_flag=True, help='Return the result as a JSON string')
def cli(apk_path, aapt, as_json):
    info_dict = get_apk_info(apk_path, as_dict=True, aapt_path=aapt)
    if as_json:
        click.echo(dumps(info_dict, indent=4))
        return
    output = 'AAPYT - CLI wrapper for aapt\n'
    for key, value in info_dict.items():
        output += f'{key.replace("_", " ").title()}: {value}\n'
    click.echo(output)

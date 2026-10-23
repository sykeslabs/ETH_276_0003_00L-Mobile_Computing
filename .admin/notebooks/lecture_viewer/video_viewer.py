"""Vintage notebook TV with browser-native power and playback controls."""
import base64
from html import escape
import json
from pathlib import Path
from runpy import run_path


def show_tv(drive_folder_id=None, drive_manifest_id=None):
    """Stream videos and captions from the public Drive channel manifest only."""
    import ipywidgets as widgets
    from IPython.display import display

    assets = Path(__file__).parent
    drive = run_path(str(assets / 'drive_video.py'))
    entries = drive['load_channels'](drive_manifest_id, drive_folder_id or drive['DEFAULT_FOLDER_ID'])
    server, url, channels = drive['serve_drive_channels'](entries)
    logo = assets.parents[1] / 'img/eth_logo.png'
    logo_html = ('<img alt="ETH Zürich" src="data:image/png;base64,'
                 + base64.b64encode(logo.read_bytes()).decode() + '">'
                 if logo.exists() else '<strong>ETH Zürich</strong>')
    page = (assets / 'tv_set.html').read_text(encoding='utf-8-sig')
    page = page.replace('/*TV_CSS*/', (assets / 'video_viewer.css').read_text(encoding='utf-8-sig'))
    page = page.replace('<!--LOGO-->', logo_html)
    page = page.replace('/*RECORDINGS*/', json.dumps(channels).replace('<', '\\u003c'))
    server.tv_page = page

    viewer = widgets.HTML(
        '<style>' + (assets / 'viewer_background.css').read_text(encoding='utf-8') + '</style>'
        + '<div style="width:85%;max-width:100%;margin:0 auto;container-type:inline-size"><iframe title="Vintage ETH lecture television" src="' + escape(url, quote=True)
        + '" allow="autoplay; fullscreen" allowfullscreen '
        + 'style="display:block;width:100%;max-width:100%;height:calc(62.5cqw + 140px);'
          'border:0;margin:0 auto;overflow:hidden;background:transparent"></iframe></div>',
        style={'background': 'transparent'},
        layout=widgets.Layout(width='100%', min_width='0', margin='0', overflow='hidden'),
    )
    viewer.add_class("eth-tv-widget")
    # Keep the serving objects tied to this viewer for the kernel session.
    viewer._tv_servers = [server]
    display(viewer)

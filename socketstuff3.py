import asyncio
import websockets
from datetime import datetime
from aiohttp import web

#async def time(websocket, path):
#    while True:
#        now = datetime.utcnow().isoformat() + 'Z'
#        await websocket.send(now)
#        await asyncio.sleep(1)

async def get_data():
    await asyncio.sleep(1)
    return "ok"

async def time(websocket, path):
    while True:
        message = await get_data()
        try:
            await websocket.send(message)
        except websockets.exceptions.ConnectionClosed:
            pass

async def index(request):
    return web.Response(
        content_type='text/html',
        text='''<!doctype html>
<script type="text/javascript" src="http://code.jquery.com/jquery-1.11.1.min.js"></script>
<script type="text/javascript">
!function(t){var i=t(window);t.fn.visible=function(t,e,o){if(!(this.length<1)){var r=this.length>1?this.eq(0):this,n=r.get(0),f=i.width(),h=i.height(),o=o?o:"both",l=e===!0?n.offsetWidth*n.offsetHeight:!0;if("function"==typeof n.getBoundingClientRect){var g=n.getBoundingClientRect(),u=g.top>=0&&g.top<h,s=g.bottom>0&&g.bottom<=h,c=g.left>=0&&g.left<f,a=g.right>0&&g.right<=f,v=t?u||s:u&&s,b=t?c||a:c&&a;if("both"===o)return l&&v&&b;if("vertical"===o)return l&&v;if("horizontal"===o)return l&&b}else{var d=i.scrollTop(),p=d+h,w=i.scrollLeft(),m=w+f,y=r.offset(),z=y.top,B=z+r.height(),C=y.left,R=C+r.width(),j=t===!0?B:z,q=t===!0?z:B,H=t===!0?R:C,L=t===!0?C:R;if("both"===o)return!!l&&p>=q&&j>=d&&m>=L&&H>=w;if("vertical"===o)return!!l&&p>=q&&j>=d;if("horizontal"===o)return!!l&&m>=L&&H>=w}}}}(jQuery);
</script>
<script type="text/javascript">
    $(document).ready(function() {
        var socket = new WebSocket('ws://' + document.domain + ':8082/');

        socket.onmessage = function(msg) {
            $("#chatlog").append('<li class="full-width ">' + msg.data + '</li>');
            while ($('#chatlog li').last().visible() === false) {
                $('#chatlog li').first().remove();
            }
        };
    });
</script>
<link rel="stylesheet" href="https://player.twitch.tv/css/player.css">
<link rel="stylesheet" href="https://web-cdn.ttvnw.net/styles/application-0fa6ef9268e043c023dfea86aeff7a02.css">
<link rel="stylesheet" href="https://cdn.betterttv.net/css/betterttv.css?v=7.0.29">
<link rel="stylesheet" href="https://cdn.betterttv.net/css/betterttv-dark.css?v=7.0.29">
<link rel="stylesheet" href="https://cdn.betterttv.net/css/betterttv-hide-recommended-channels.css?v=7.0.29">
<link rel="stylesheet" href="https://web-cdn.ttvnw.net/styles/twilight/core-4a4a70c7c2b9d9ebcbcad1b8c739ad36.css">
<style>
    body {
        overflow:hidden;
    }
</style>
<title>Twitch chat</title>
<div class=page>
    <ul id="chatlog" class="full-width align-items-end flex" style="min-height: 0px;"></ul>
</div>''',
    )

socket_server = websockets.serve(time, '127.0.0.1', 8082)
web_server = web.Server(index)
asyncio.get_event_loop().run_until_complete(
    asyncio.get_event_loop().create_server(web_server, '127.0.0.1', 8083)
)

asyncio.get_event_loop().run_until_complete(socket_server)
asyncio.get_event_loop().run_forever()

import urllib
from contextlib import asynccontextmanager
from urllib.parse import urlparse, parse_qs, unquote_plus

from aiohttp import ClientResponse
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from fastapi import FastAPI, Request, HTTPException
from pydantic import AnyUrl, AnyHttpUrl
from manager import RotatingSessionManager

session_manager = RotatingSessionManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    global session_manager
    await session_manager.startup_event()
    yield
    await session_manager.close_sessions()


app = FastAPI(lifespan=lifespan)


@app.get("/")
async def proxy(url: str, request: Request):
    try:
        url = unquote_plus(url)

        cookies = request.cookies.items()
        session = await session_manager.get_session(url=url)
        response: ClientResponse = await session.get(url, cookies=cookies)

        if response.status != 200:
            raise HTTPException(status_code=response.status, detail="Failed to fetch data")

        content_type = response.headers.get("Content-Type", "")

        if "application/json" in content_type:
            data = await response.json()
            return JSONResponse(content=data)

        elif "text/html" in content_type:
            data = await response.text()
            return HTMLResponse(content=data)

        data = await response.text()
        return PlainTextResponse(content=data)

    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8001)

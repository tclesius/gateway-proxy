import argparse
import os
from contextlib import asynccontextmanager
from urllib.parse import unquote_plus
from aiohttp import ClientResponse
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from fastapi import FastAPI, Request, HTTPException
from manager import RotatingSessionManager

aws_access_key_id = os.environ.get('AWS_ACCESS_KEY_ID')
aws_secret_access_key = os.environ.get('AWS_SECRET_ACCESS_KEY')
targets = os.environ.get('TARGETS')
verbose = os.environ.get('VERBOSE', False)

session_manager = RotatingSessionManager(
    aws_access_key_id=aws_access_key_id,
    aws_secret_access_key=aws_secret_access_key,
    targets=targets.split() if targets else None,
    verbose=verbose
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global session_manager
    await session_manager.startup_event()
    yield
    await session_manager.shutdown_event()


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

    uvicorn.run(app, host="0.0.0.0", port=8000)

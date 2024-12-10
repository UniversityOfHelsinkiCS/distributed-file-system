import os
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from fastapi.templating import Jinja2Templates
from fastapi.responses import FileResponse
from redis import Redis

from .constants import FILE_DIRECTORY
from .logger import logger
from .raft_node import LogEntry
from .redis_client import get_redis_store

router = APIRouter()

templates = Jinja2Templates(directory="app/templates")


@router.post("/upload")
async def upload(request: Request, file: UploadFile):
    if not file.size or not file.filename:
        raise HTTPException(status_code=400, detail="File is empty")
    try:
        file_path = Path(os.path.join(FILE_DIRECTORY, file.filename))
        if file_path.is_file():
            raise FileExistsError

        contents = await file.read()
        with open(os.path.join(FILE_DIRECTORY, file.filename), "wb") as f:
            f.write(contents)

        command = {
            "operation": "upload",
            "filename": file.filename,
            "content_type": file.content_type,
            "file_size": len(contents),
        }
        await request.app.raft_node.add_command(command)

    except FileExistsError:
        raise HTTPException(
            status_code=409, detail="File already exists, rename the file and try again"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Something went wrong: {e}")
    finally:
        await file.close()

    return {"message": f"Successfully uploaded {file.filename}"}


@router.get("/get/{filename}")
async def get(filename: str):
    file = Path(os.path.join(FILE_DIRECTORY, filename))
    if not file.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    try:
        return FileResponse(os.path.join(FILE_DIRECTORY, filename), filename=filename)
    except Exception:
        raise HTTPException(status_code=500, detail="Something went wrong")


@router.get("/")
async def main(request: Request, store: Redis = Depends(get_redis_store)):
    try:
        raft_log = await store.lrange("raft_log", 0, -1)
        files = []

        for entry in raft_log:
            filename = LogEntry.from_json(entry).command["filename"]
            files.append(filename)

        return templates.TemplateResponse(
            request=request, name="index.html", context={"file_list": files}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Something went wrong: {e}")


@router.get("/ping")
async def ping():
    logger.info("RECEIVED PING")
    return {"message": "pong"}

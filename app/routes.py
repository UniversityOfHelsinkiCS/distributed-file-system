import os
from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel
from typing import Dict, Any
from .redis_client import get_redis_store

FILE_DIRECTORY = "storage"

router = APIRouter()


@router.post("/upload")
async def upload(file: UploadFile, store=Depends(get_redis_store)):
    try:
        filename_hash = hash(file.filename)
        exists = await store.exists(filename_hash)
        if exists:
            raise FileExistsError

        contents = await file.read()
        with open(os.path.join(FILE_DIRECTORY, file.filename), "wb") as f:
            f.write(contents)

        file_metadata = {
            "filename": file.filename,
            "content_type": file.content_type,
            "file_size": len(contents),
        }
        await store.hmset(filename_hash, file_metadata)

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
    try:
        return FileResponse(os.path.join(FILE_DIRECTORY, filename), filename=filename)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found")
    except Exception:
        raise HTTPException(status_code=500, detail="Something went wrong")


@router.get("/")
async def main(store=Depends(get_redis_store)):
    try:
        keys = await store.keys("*")
        files = []
        for key in keys:
            metadata = await store.hgetall(key)
            files.append(metadata.get("filename", "Unknown"))

        file_list = "<ul>" + "".join(f"<li>{file}</li>" for file in files) + "</ul>"
        content = f"""
        <body>
            <h2>Upload a new file:</h2>
            <form action="/upload" enctype="multipart/form-data" method="post">
                <input name="file" type="file">
                <input type="submit">
            </form>
            
            <h2>Uploaded Files:</h2>
            {file_list}
        </body>
        """
        return HTMLResponse(content=content)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Something went wrong: {e}")


@router.get("/ping")
async def ping():
    print("RECEIVED PING")
    return {"message": "pong"}


async def heartbeat():
    print("received heartbeat")


class RPCRequest(BaseModel):
    method: str
    params: Dict[str, Any]


rpc_methods = {
    "heartbeat": heartbeat,
}


@router.post("/rpc")
async def rpc_handler(request: RPCRequest):
    method = rpc_methods.get(request.method)
    if not method:
        raise HTTPException(status_code=400, detail="Method not found")

    try:
        # Call the method with the provided parameters
        result = await method(**request.params)
        return {"result": result}
    except TypeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid parameters: {e}")

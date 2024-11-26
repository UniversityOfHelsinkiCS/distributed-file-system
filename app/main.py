import os
from threading import Thread

import time
from fastapi import Depends, FastAPI, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse

from .raft_node import RaftNode
from .redis_client import get_redis_store

FILE_DIRECTORY = "storage"

is_leader = os.environ.get("LEADER") == "true"
print(is_leader)

raft_node = RaftNode(
    1,
    ["app-2:8000", "app-3:8000"],  # Corrected hostnames
    is_leader,
)

if not os.path.exists(FILE_DIRECTORY):
    os.makedirs(FILE_DIRECTORY)

app = FastAPI()


@app.post("/upload")
async def upload(file: UploadFile, store=Depends(get_redis_store)):
    try:
        filename_hash = hash(file.filename)
        exists = await store.exists(filename_hash)
        if exists:
            raise FileExistsError

        contents = file.file.read()
        with open(os.path.join(FILE_DIRECTORY, file.filename), "wb") as f:
            f.write(contents)

        file_metadata = {
            "filename": file.filename,
            "content_type": file.content_type,
            "file_size": file.size,
        }
        await store.hmset(filename_hash, file_metadata)

    except FileExistsError:
        raise HTTPException(
            status_code=409, detail="File already exists, rename the file and try again"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Something went wrong: {e}")
    finally:
        file.file.close()

    return {"message": f"Successfully uploaded {file.filename}"}


@app.get("/get/{filename}")
async def get(filename: str):
    try:
        return FileResponse(os.path.join(FILE_DIRECTORY, filename), filename=filename)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found")
    except Exception:
        raise HTTPException(status_code=500, detail="Something went wrong")


@app.get("/")
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


@app.get("/ping")
async def ping():
    print("RECEIVED PING")
    return {"message": "pong"}


def background_task():
    while True:
        raft_node.run()
        time.sleep(5)


t = Thread(target=background_task)
t.start()

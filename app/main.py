from contextlib import asynccontextmanager
import os

from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse

from redis_client import setup

FILE_DIRECTORY = "storage"


@asynccontextmanager
async def lifespan(application: FastAPI):
    if not os.path.exists(FILE_DIRECTORY):
        os.makedirs(FILE_DIRECTORY)

    try:
        application.state.redis = await setup()
        yield
    finally:
        await application.state.redis.close()


app = FastAPI(lifespan=lifespan)


@app.post("/upload")
async def upload(file: UploadFile):
    try:
        contents = file.file.read()
        with open(os.path.join(FILE_DIRECTORY, file.filename), "wb") as f:
            f.write(contents)

        filename_hash = hash(file.filename)
        file_metadata = {
            "filename": file.filename,
            "hash": filename_hash,
            "content_type": file.content_type,
            "file_size": len(contents),
        }
        await app.state.redis.hmset(filename_hash, file_metadata)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Something went wrong: {e}")
    finally:
        file.file.close()

    return {"message": f"Successfully uploaded {file.filename}"}


@app.get("/get/{file_name}")
async def get(file_name: str):
    try:
        file_metadata = await app.state.redis.hgetall(hash(file_name))
        print(file_metadata)

        return FileResponse(os.path.join(FILE_DIRECTORY, file_name), filename=file_name)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found")
    except Exception:
        raise HTTPException(status_code=500, detail="Something went wrong")


@app.get("/")
async def main():
    content = """
    <body>
        <form action="/upload" enctype="multipart/form-data" method="post">
            <input name="file" type="file">
            <input type="submit">
        </form>
    </body>
    """
    return HTMLResponse(content=content)

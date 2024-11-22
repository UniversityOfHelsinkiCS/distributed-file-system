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
        filename_hash = hash(file.filename)
        exists = await app.state.redis.exists(filename_hash)
        if exists:
            raise FileExistsError

        contents = file.file.read()
        with open(os.path.join(FILE_DIRECTORY, file.filename), "wb") as f:
            f.write(contents)

        file_metadata = {
            "filename": file.filename,
            "content_type": file.content_type,
            "file_size": len(contents),
        }
        await app.state.redis.hmset(filename_hash, file_metadata)

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
async def main():
    try:
        keys = await app.state.redis.keys("*")
        files = []
        for key in keys:
            metadata = await app.state.redis.hgetall(key)
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

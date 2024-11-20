import os

from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse

app = FastAPI()

FILE_DIRECTORY = "../storage"

if not os.path.exists(FILE_DIRECTORY):
    os.makedirs(FILE_DIRECTORY)


@app.post("/upload")
async def upload(file: UploadFile):
    try:
        contents = file.file.read()
        with open(os.path.join(FILE_DIRECTORY, file.filename), "wb") as f:
            f.write(contents)
    except Exception:
        raise HTTPException(status_code=500, detail="Something went wrong")
    finally:
        file.file.close()

    return {"message": f"Successfully uploaded {file.filename}"}


@app.get("/get/{file_name}")
async def get(file_name: str):
    try:
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

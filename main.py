from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, PlainTextResponse
import requests
import asyncio
import os

app = FastAPI()

# ---------- PROVIDERS ----------

async def yougetsignal(ip):
    try:
        res = requests.post(
            "https://domains.yougetsignal.com/domains.php",
            headers={
                "content-type":"application/x-www-form-urlencoded",
                "user-agent":"Mozilla/5.0",
                "origin":"https://www.yougetsignal.com",
                "referer":"https://www.yougetsignal.com/tools/web-sites-on-web-server/"
            },
            data=f"remoteAddress={ip}&key=&_",
            timeout=10
        )

        if '"status":"Fail"' in res.text:
            return f"[ {ip} ] -> Rate Limit / Blocked"

        js = res.json()
        arr = js.get("domainArray", [])
        if not arr:
            return f"[ {ip} ] -> No Domains"

        domains = "\n".join([d[0] for d in arr])
        return f"[ {ip} ] ({len(arr)} domains)\n{domains}"

    except:
        return f"[ {ip} ] -> Error / Timeout"

async def hackertarget(ip):
    try:
        res = requests.get(
            f"https://api.hackertarget.com/reverseiplookup/?q={ip}",
            timeout=10
        )
        txt = res.text
        if "error" in txt.lower() or "No DNS" in txt:
            return f"[ {ip} ] -> No Result"
        return f"[ {ip} ]\n{txt}"
    except:
        return f"[ {ip} ] -> Error"

async def resolve(ip, provider):
    if provider == "yougetsignal":
        return await yougetsignal(ip)
    if provider == "hackertarget":
        return await hackertarget(ip)

    # fallback auto
    r = await yougetsignal(ip)
    if "Rate Limit" in r or "Error" in r:
        r = await hackertarget(ip)
    return r


# ---------- API ----------

@app.get("/")
async def ui():
    return HTMLResponse(open("index.html","r").read())

@app.post("/scan")
async def scan(request: Request):
    data = await request.json()
    ips = data["ips"]
    provider = data["provider"]

    tasks = []
    results = []

    # brutal mode parallel (limited to 8)
    sem = asyncio.Semaphore(8)

    async def worker(ip):
        async with sem:
            result = await resolve(ip, provider)
            results.append(result)

    for ip in ips:
        asyncio.create_task(worker(ip))

    await asyncio.sleep(0.1)
    await asyncio.gather(*asyncio.all_tasks() - {asyncio.current_task()})

    return PlainTextResponse("\n\n".join(results))
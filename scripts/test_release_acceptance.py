"""Bounded acceptance check against the isolated Compose CI instance, never a public host."""
import concurrent.futures
import http.cookiejar
import json
import ssl
import statistics
import time
from urllib.error import HTTPError
from urllib.request import Request, build_opener, HTTPSHandler, HTTPCookieProcessor
from uuid import uuid4

BASE="https://localhost:8443"
CA="/tmp/arak-test-ca.crt"
CTX=ssl.create_default_context(cafile=CA)

def client():
    jar=http.cookiejar.CookieJar()
    return build_opener(HTTPSHandler(context=CTX),HTTPCookieProcessor(jar)),jar

def request(opener,path,body=None,csrf=None):
    headers={"Accept":"application/json"}
    if body is not None:
        headers.update({"Content-Type":"application/json","Origin":BASE,"Referer":BASE+"/"})
        if csrf: headers["X-CSRFToken"]=csrf
    try:
        response=opener.open(Request(BASE+path,headers=headers,data=json.dumps(body).encode() if body is not None else None),timeout=15)
    except HTTPError as error:
        response=error
    with response:
        raw=response.read()
        return response.status,response.headers,raw

def token(jar):
    return next(c.value for c in jar if c.name=="csrftoken")

def register(phone):
    opener,jar=client()
    status,headers,_=request(opener,"/")
    assert status==200
    csrf=next(c for c in jar if c.name=="csrftoken")
    assert csrf.secure
    assert "max-age" in headers.get("Strict-Transport-Security","").lower()
    data={"name":"Acceptance fixture","phone":phone,"alias":"","password":uuid4().hex}
    assert request(opener,"/api/auth/register",data)[0]==403
    status,headers,_=request(opener,"/api/auth/register",data,token(jar))
    assert status==201,status
    session=next(c for c in jar if c.name=="sessionid")
    assert session.secure and session.has_nonstandard_attr("HttpOnly")
    return opener,jar

def order(session,phone,pid):
    opener,jar=session
    body={"full_name":"Acceptance fixture","phone":phone,"address":"Fixture only","items":[{"product_id":pid,"quantity":1}],"token":str(uuid4())}
    result=request(opener,"/api/orders",body,token(jar))
    return result,body

anonymous,_=client()
assert request(anonymous,"/api/me")[0]==401
assert request(anonymous,"/api/admin/products")[0]==401
items=json.loads(request(anonymous,"/api/products")[2])["products"]
pid=next(x["id"] for x in items if x["name"]=="Release acceptance fixture")
phones=["09120000971","09120000972"]
sessions=[register(phone) for phone in phones]
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
    results=list(pool.map(lambda i:order(sessions[i],phones[i],pid),range(2)))
assert sorted(x[0][0] for x in results)==[201,409], [x[0][0] for x in results]
winner=next(i for i,x in enumerate(results) if x[0][0]==201)
opener,jar=sessions[winner]
original=json.loads(results[winner][0][2])
replay=request(opener,"/api/orders",results[winner][1],token(jar))
assert replay[0]==201 and json.loads(replay[2])["id"]==original["id"]
assert json.loads(request(anonymous,f"/api/products/{pid}")[2])["stock"]==0
for i,(opener,jar) in enumerate(sessions):
    data=json.loads(request(opener,"/api/orders")[2])["orders"]
    assert len(data)==(1 if i==winner else 0)
print("PASS verified TLS, secure cookies, CSRF, anonymous access, concurrent last-item sale, idempotent replay, account isolation")

# Small fixed CI-only read load: no external endpoint or production benchmark.
routes=["/","/products/","/api/products","/api/ready"]
def read(i):
    opener,_=client()
    start=time.perf_counter()
    status,_,_=request(opener,routes[i%len(routes)])
    assert status==200,status
    return (time.perf_counter()-start)*1000
with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
    samples=sorted(pool.map(read,range(80)))
print(f"PASS 80 isolated reads / 8 workers; median {statistics.median(samples):.1f} ms; p95 {samples[75]:.1f} ms")

"""Sandbox transport only. Never sends customer data or calls a live payment host."""
import json
import re
from urllib.request import Request,build_opener,HTTPRedirectHandler
from urllib.error import URLError
from django.conf import settings

BASE="https://sandbox.zarinpal.com/pg/"
AUTHORITY=re.compile(r"[A-Za-z0-9_-]{1,80}\Z")
REFERENCE=re.compile(r"[A-Za-z0-9_-]{1,80}\Z")

class GatewayError(Exception):
    pass

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        return None

def call(endpoint,payload):
    if not settings.ARAK_SANDBOX_PAYMENTS or endpoint not in {"request","verify"}:
        raise GatewayError("Sandbox disabled")
    data={"merchant_id":settings.ARAK_SANDBOX_MERCHANT_ID,**payload}
    request=Request(BASE+"v4/payment/"+endpoint+".json",data=json.dumps(data).encode(),headers={"Content-Type":"application/json","Accept":"application/json"},method="POST")
    try:
        with build_opener(NoRedirect()).open(request,timeout=10) as response:
            raw=response.read(65537)
        if len(raw)>65536: raise GatewayError("Oversize response")
        parsed=json.loads(raw)
        result=parsed.get("data") if isinstance(parsed,dict) else None
        if not isinstance(result,dict): raise GatewayError("Invalid response")
        return result
    except (OSError,URLError,ValueError,RecursionError):
        raise GatewayError("Sandbox response unavailable") from None

def create_payment(amount,callback):
    result=call("request",{"amount":amount,"currency":"IRR","callback_url":callback,"description":"Arak Kala isolated sandbox test"})
    authority=result.get("authority")
    if result.get("code")!=100 or not isinstance(authority,str) or not AUTHORITY.fullmatch(authority):
        raise GatewayError("Sandbox request not accepted")
    return authority

def verify_payment(amount,authority):
    result=call("verify",{"amount":amount,"authority":authority})
    if result.get("code") not in (100,101):
        raise GatewayError("Sandbox not verified")
    ref=result.get("ref_id")
    if type(ref) not in (int,str) or not REFERENCE.fullmatch(str(ref)) or str(ref)=="0":
        raise GatewayError("Invalid sandbox reference")
    return str(ref)

def payment_url(authority):
    if not AUTHORITY.fullmatch(authority): raise GatewayError("Invalid authority")
    return BASE+"StartPay/"+authority

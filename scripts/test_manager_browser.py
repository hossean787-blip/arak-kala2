"""Browser verification of the real owner management panel, isolated test DB only."""
import os
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import urlopen
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor
import django
from playwright.sync_api import sync_playwright, expect
from PIL import Image

if os.environ.get("ARAK_DEVELOPMENT") != "1" or os.environ.get("ARAK_DB_PATH") != "/tmp/arak-browser-test.sqlite3" or os.environ.get("ARAK_MEDIA_ROOT") != "/tmp/arak-browser-media":
    raise SystemExit("Use isolated CI browser fixture environment only.")
sys.path.insert(0,str(Path.cwd()))
os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings")
django.setup()
from django.conf import settings
from django.contrib.auth import get_user_model
from store.models import Product, StockMovement

phrase=uuid4().hex
get_user_model().objects.create_user(settings.STORE_MANAGER_EMAIL,email=settings.STORE_MANAGER_EMAIL,password=phrase)
fixtures={width:Product.objects.create(sku=f"MANAGER-BROWSER-{width}",name=f"کالای آزمایشی مدیریت {width}",price=1500000,stock=4).pk for width in (390,1440)}
def check_mutation(pk):
    product=Product.objects.get(pk=pk)
    assert product.stock==2 and len(product.images)==1
    assert StockMovement.objects.filter(product=product,delta=-2).exists()

out=Path("browser-artifacts")
out.mkdir(exist_ok=True)
sample=Path("/tmp/arak-manager-fixture.png")
Image.new("RGB",(180,320),"#cab9a7").save(sample)
server=subprocess.Popen([sys.executable,"manage.py","runserver","127.0.0.1:8765","--noreload"],stdout=subprocess.DEVNULL,stderr=subprocess.STDOUT)
try:
    base="http://127.0.0.1:8765"
    for _ in range(60):
        try:
            with urlopen(base+"/api/health",timeout=1) as response:
                if response.status==200: break
        except OSError: time.sleep(.25)
    else: raise RuntimeError("Django did not start")
    with sync_playwright() as p:
        browser=p.chromium.launch()
        for width,height in [(390,844),(1440,1000)]:
            pk=fixtures[width]
            page=browser.new_page(viewport={"width":width,"height":height})
            errors=[]
            page.on("pageerror",lambda error:errors.append(str(error)))
            page.goto(base+"/manager/login/")
            page.locator("input[name=username]").fill(settings.STORE_MANAGER_EMAIL)
            page.locator("input[name=password]").fill(phrase)
            page.locator(".form-stack button").click()
            expect(page.locator("h1")).to_have_text("مدیریت فروشگاه")
            page.screenshot(path=out/f"manager-dashboard-{width}.png",full_page=True,animations="disabled")
            page.goto(base+f"/manager/products/?q=MANAGER-BROWSER-{width}")
            expect(page.locator(".manager-product")).to_have_count(1)
            page.screenshot(path=out/f"manager-products-{width}.png",full_page=True,animations="disabled")
            page.get_by_role("link",name="تصاویر",exact=True).click()
            page.locator("input[type=file]").set_input_files(str(sample))
            page.get_by_role("button",name="بارگذاری تصویر").click()
            expect(page.locator(".manager-preview img")).to_have_count(1)
            page.screenshot(path=out/f"manager-images-{width}.png",full_page=True,animations="disabled")
            page.goto(base+f"/manager/products/{pk}/adjust/")
            page.locator("input[name=desired]").fill("2")
            page.locator("input[name=reason]").fill("اصلاح آزمایشی مرورگر")
            page.locator(".form-stack button").click()
            expect(page.locator("h1")).to_have_text("کالا و موجودی")
            with ThreadPoolExecutor(max_workers=1) as executor:
                executor.submit(check_mutation,pk).result()
            page.goto(base+"/manager/inventory/")
            expect(page.locator("table")).to_contain_text("اصلاح آزمایشی مرورگر")
            page.goto(base+"/manager/reports/")
            expect(page.locator("h1")).to_have_text("گزارش عملکرد فروشگاه")
            page.screenshot(path=out/f"manager-report-{width}.png",full_page=True,animations="disabled")
            for route in ["/manager/","/manager/products/","/manager/inventory/","/manager/orders/","/manager/reports/"]:
                response=page.goto(base+route)
                assert response.status==200,(route,response.status)
                assert page.evaluate("document.documentElement.scrollWidth<=innerWidth+1"),(route,width)
            assert not errors,errors
            page.close()
            print(f"PASS manager {width}px: auth, navigation, image upload, inventory, reports",flush=True)
        browser.close()
finally:
    server.terminate()
    server.wait(timeout=15)

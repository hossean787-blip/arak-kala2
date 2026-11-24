"""Real Chromium smoke test against a Django server with isolated fixtures."""
import os
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import urlopen
import django
from PIL import Image, ImageDraw
from playwright.sync_api import sync_playwright, expect

if os.environ.get("ARAK_DEVELOPMENT") != "1" or os.environ.get("ARAK_DB_PATH") != "/tmp/arak-browser-test.sqlite3" or os.environ.get("ARAK_MEDIA_ROOT") != "/tmp/arak-browser-media":
    raise SystemExit("Use isolated CI browser fixture environment only.")
sys.path.insert(0, str(Path.cwd()))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()
from django.conf import settings
from store.models import Product

out = Path("browser-artifacts")
out.mkdir(exist_ok=True)
media = settings.MEDIA_ROOT / "browser-fixtures"
media.mkdir(parents=True, exist_ok=True)
for label,size,color in [("portrait",(360,720),"#d8ccba"),("landscape",(720,360),"#b9c3b8"),("square",(480,480),"#cbb6ac")]:
    image=Image.new("RGB",size,color)
    draw=ImageDraw.Draw(image)
    w,h=size
    draw.rounded_rectangle((w*.18,h*.18,w*.82,h*.82),radius=18,fill="#393a35")
    draw.rectangle((w*.40,h*.38,w*.60,h*.62),fill="#e5dfd0")
    image.save(media/f"{label}.png")
Product.objects.create(sku="visual-portrait",name="کالای آزمایشی عمودی با عنوان طولانی برای بررسی چیدمان",category="پوشاک",price=1200000,stock=4,images=["browser-fixtures/portrait.png","browser-fixtures/square.png"])
Product.objects.create(sku="visual-landscape",name="کالای آزمایشی افقی",category="اکسسوری",price=880000,stock=2,images=["browser-fixtures/landscape.png"])
Product.objects.create(sku="visual-missing",name="کالای آزمایشی بدون تصویر",category="اکسسوری",price=250000,stock=0)
Product.objects.create(sku="visual-square",name="کالای آزمایشی مربع",category="پوشاک",price=940000,stock=5,images=["browser-fixtures/square.png"])
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
        for width,height in [(320,720),(360,800),(390,844),(768,1024),(1440,1000)]:
            page=browser.new_page(viewport={"width":width,"height":height},device_scale_factor=1)
            errors=[]
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(base,wait_until="domcontentloaded")
            expect(page.locator(".hero")).to_be_visible()
            page.screenshot(path=out/f"home-{width}.png",full_page=True,animations="disabled")
            page.goto(base+"/products/")
            expect(page.locator(".product-card")).to_have_count(4)
            page.locator(".product-photo img").evaluate_all("(images)=>Promise.all(images.map(i=>{i.loading='eager';return i.decode()}))")
            assert page.locator(".product-photo").evaluate_all("(nodes)=>nodes.every(n=>Math.abs(n.clientWidth/n.clientHeight-.8)<.03)")
            assert page.locator(".product-photo img").evaluate_all("(nodes)=>nodes.length===3 && nodes.every(n=>getComputedStyle(n).objectFit==='contain' && n.naturalWidth>0)")
            if width<=640:
                assert page.locator(".product-grid").evaluate("e=>getComputedStyle(e).gridTemplateColumns.split(' ').length")==2
                expect(page.locator(".bottom-nav")).to_be_visible()
            page.screenshot(path=out/f"catalog-{width}.png",full_page=True,animations="disabled")
            page.locator("input[name=q]").fill("عمودی")
            page.locator(".public-filter button").click()
            expect(page.locator(".product-card")).to_have_count(1)
            page.locator(".product-photo").click()
            assert "/products/" in page.url
            expect(page.locator(".gallery-thumb")).to_have_count(2)
            page.locator(".gallery-thumb").nth(1).click()
            expect(page.locator("#galleryMain img")).to_have_attribute("src","/uploads/browser-fixtures/square.png")
            page.screenshot(path=out/f"product-{width}.png",full_page=True,animations="disabled")
            page.get_by_role("button",name="افزودن به سبد خرید").click()
            expect(page.locator(".public-cart-row")).to_have_count(1)
            page.reload()
            expect(page.locator(".public-cart-row")).to_have_count(1)
            page.get_by_role("link",name="ادامه ثبت سفارش").click()
            expect(page.locator("input[name=customer]")).to_be_visible()
            for route in ["/categories/","/search/","/favorites/","/login/","/register/","/tracking/","/about/","/contact/","/terms/","/privacy/","/account/","/account/orders/","/account/addresses/"]:
                response=page.goto(base+route,wait_until="domcontentloaded")
                assert response.status==200, (route,response.status)
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth+1"),(route,width)
                expect(page.locator("main h1")).to_be_visible()
            assert not errors,errors
            page.close()
            print(f"PASS {width}px: independent routes, media, search, gallery, persistent cart, checkout, auth",flush=True)
        browser.close()
finally:
    server.terminate()
    server.wait(timeout=15)

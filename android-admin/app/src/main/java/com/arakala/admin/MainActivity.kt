package com.arakala.admin

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.net.Uri
import android.os.Bundle
import android.util.Base64
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.PickVisualMediaRequest
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalLayoutDirection
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.LayoutDirection
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import org.json.JSONArray
import org.json.JSONObject
import java.io.ByteArrayOutputStream
import java.net.HttpURLConnection
import java.net.URL

private val Ink = Color(0xFF171717)
private val Cream = Color(0xFFF8F7F4)
private val Orange = Color(0xFFED6C48)
private val Soft = Color(0xFFF0EEE8)

class MainActivity : ComponentActivity() {
    private val api = ShopApi()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            MaterialTheme(colorScheme = lightColorScheme(primary = Ink, onPrimary = Color.White, background = Cream, surface = Color.White)) {
                CompositionLocalProvider(LocalLayoutDirection provides LayoutDirection.Rtl) {
                    AdminScreen(api, ::onImageBytes, this@MainActivity)
                }
            }
        }
    }

    private fun onImageBytes(uri: Uri): ByteArray {
        val bitmap = contentResolver.openInputStream(uri)?.use { BitmapFactory.decodeStream(it) }
            ?: error("تصویر انتخاب‌شده قابل خواندن نیست")
        val maxSide = maxOf(bitmap.width, bitmap.height)
        val scale = minOf(1f, 1400f / maxSide)
        val reduced = if (scale == 1f) bitmap else Bitmap.createScaledBitmap(
            bitmap, (bitmap.width * scale).toInt().coerceAtLeast(1), (bitmap.height * scale).toInt().coerceAtLeast(1), true
        )
        val result = ByteArrayOutputStream()
        reduced.compress(Bitmap.CompressFormat.JPEG, 78, result)
        return result.toByteArray().also { require(it.size <= 2 * 1024 * 1024) { "حجم تصویر بیش از ۲ مگابایت است" } }
    }
}

/** The demo keeps the token in memory (cleared on process exit), never in a plain-text preference. */
private class ShopApi {
    var token: String = ""
    private fun request(path: String, method: String = "GET", body: JSONObject? = null): JSONObject {
        val connection = URL(BuildConfig.API_BASE_URL + path).openConnection() as HttpURLConnection
        try {
            connection.requestMethod = method
            connection.instanceFollowRedirects = false
            connection.connectTimeout = 12000
            connection.readTimeout = 12000
            connection.setRequestProperty("Accept", "application/json")
            if (token.isNotBlank()) connection.setRequestProperty("Authorization", "Bearer $token")
            if (body != null) {
                connection.doOutput = true
                connection.setRequestProperty("Content-Type", "application/json; charset=utf-8")
                connection.outputStream.use { it.write(body.toString().toByteArray(Charsets.UTF_8)) }
            }
            val raw = (if (connection.responseCode in 200..299) connection.inputStream else connection.errorStream)
                ?.bufferedReader(Charsets.UTF_8)?.use { it.readText() } ?: "{}"
            val result = JSONObject(raw)
            if (connection.responseCode !in 200..299) error(result.optString("error", "خطای ارتباط با سرور"))
            return result
        } finally { connection.disconnect() }
    }

    fun login(email: String, password: String) {
        val result = request("/admin/session", "POST", JSONObject().put("email", email).put("password", password))
        if (result.getJSONObject("user").getString("role") != "admin") error("این برنامه فقط برای مدیر اراک کالاست")
        token = result.getString("token")
    }
    fun logout() {
        try {
            request("/admin/logout", "POST")
        } finally {
            token = ""
        }
    }
    fun stats(): JSONObject = request("/admin/stats")
    fun products(): JSONArray = request("/admin/products").getJSONArray("products")
    fun orders(): JSONArray = request("/admin/orders").getJSONArray("orders")
    fun upload(bytes: ByteArray): String = request("/admin/images", "POST", JSONObject()
        .put("mime", "image/jpeg").put("base64", Base64.encodeToString(bytes, Base64.NO_WRAP))).getString("url")
    fun saveProduct(id: Int?, payload: JSONObject) {
        if (id == null) request("/admin/products", "POST", payload)
        else request("/admin/products/$id", "PATCH", payload)
    }
    fun deactivateProduct(id: Int) { request("/admin/products/$id", "DELETE") }
    fun advanceOrder(id: Int, status: String) {
        request("/admin/orders/$id/status", "PATCH", JSONObject().put("status", status))
    }
}

@Composable
private fun AdminScreen(api: ShopApi, imageBytes: (Uri) -> ByteArray, activity: MainActivity) {
    var isLoggedIn by remember { mutableStateOf(false) }
    var page by remember { mutableStateOf("dashboard") }
    var busy by remember { mutableStateOf(false) }
    var message by remember { mutableStateOf("") }
    var stats by remember { mutableStateOf(JSONObject()) }
    var products by remember { mutableStateOf(JSONArray()) }
    var orders by remember { mutableStateOf(JSONArray()) }
    var editing by remember { mutableStateOf<JSONObject?>(null) }

    // All network calls are on worker threads. Compose state updates occur on the UI thread.
    fun perform(task: () -> Unit, success: () -> Unit = {}) {
        if (busy) return
        busy = true; message = ""
        Thread {
            try { task(); activity.runOnUiThread { busy = false; success() } }
            catch (e: Exception) { activity.runOnUiThread { busy = false; message = e.message ?: "خطای غیرمنتظره" } }
        }.start()
    }
    fun reload() {
        var newStats = JSONObject()
        var newProducts = JSONArray()
        var newOrders = JSONArray()
        perform({ newStats = api.stats(); newProducts = api.products(); newOrders = api.orders() }) {
            stats = newStats; products = newProducts; orders = newOrders
        }
    }

    Surface(modifier = Modifier.fillMaxSize(), color = Cream) {
        Column(modifier = Modifier.fillMaxSize().systemBarsPadding()) {
            if (!isLoggedIn) {
                LoginPanel(busy, message) { email, pass ->
                    perform({ api.login(email, pass) }) { isLoggedIn = true; reload() }
                }
            } else {
                Row(modifier = Modifier.fillMaxWidth().padding(horizontal = 20.dp, vertical = 14.dp),
                    horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                    Text("ARAK  KALA.", fontSize = 20.sp, fontWeight = FontWeight.Black, color = Ink)
                    TextButton(enabled = !busy, onClick = {
                        perform({ runCatching { api.logout() } }) {
                            isLoggedIn = false
                            page = "dashboard"
                            stats = JSONObject()
                            products = JSONArray()
                            orders = JSONArray()
                            editing = null
                        }
                    }) { Text("خروج") }
                }
                if (busy) LinearProgressIndicator(modifier = Modifier.fillMaxWidth(), color = Orange)
                if (message.isNotBlank()) Text(message, color = Orange, modifier = Modifier.padding(horizontal = 20.dp))
                if (page == "edit") {
                    ProductEditor(editing, busy, onBack = { page = "products" }, onSave = { json, images ->
                        perform({
                            val old = editing?.optJSONArray("images") ?: JSONArray()
                            val all = JSONArray()
                            for (i in 0 until old.length()) all.put(old.getString(i))
                            images.forEach { if (all.length() < 8) all.put(api.upload(imageBytes(it))) }
                            json.put("images", all)
                            api.saveProduct(editing?.getInt("id"), json)
                        }) { message = "محصول ذخیره شد"; page = "products"; reload() }
                    })
                } else {
                    Row(modifier = Modifier.fillMaxWidth().padding(horizontal = 14.dp), horizontalArrangement = Arrangement.spacedBy(5.dp)) {
                        TabButton("داشبورد", page == "dashboard", Modifier.weight(1f)) { page = "dashboard"; reload() }
                        TabButton("محصولات", page == "products", Modifier.weight(1f)) { page = "products"; reload() }
                        TabButton("سفارش‌ها", page == "orders", Modifier.weight(1f)) { page = "orders"; reload() }
                    }
                    when (page) {
                        "dashboard" -> Dashboard(stats, onProducts = { page = "products" }, onOrders = { page = "orders" }, onRefresh = { reload() })
                        "products" -> ProductsPanel(products, onAdd = { editing = null; page = "edit" }, onEdit = { editing = it; page = "edit" },
                            onDelete = { id -> perform({ api.deactivateProduct(id) }) { reload() } })
                        "orders" -> OrdersPanel(orders, onChange = { id, next -> perform({ api.advanceOrder(id,next) }) { reload() } })
                    }
                }
            }
        }
    }
}

@Composable
private fun TabButton(label: String, chosen: Boolean, modifier: Modifier, onClick: () -> Unit) {
    Button(onClick = onClick, modifier = modifier, shape = RoundedCornerShape(9.dp),
        colors = ButtonDefaults.buttonColors(containerColor = if (chosen) Ink else Soft, contentColor = if (chosen) Color.White else Ink),
        contentPadding = PaddingValues(horizontal = 4.dp)) { Text(label, fontSize = 11.sp) }
}

@Composable
private fun LoginPanel(busy: Boolean, message: String, onLogin: (String, String) -> Unit) {
    var email by remember { mutableStateOf("") }; var password by remember { mutableStateOf("") }
    Column(modifier = Modifier.fillMaxSize().padding(28.dp), verticalArrangement = Arrangement.Center) {
        Text("ARAK", fontWeight = FontWeight.Black, fontSize = 54.sp, lineHeight = 50.sp)
        Text("KALA.", fontWeight = FontWeight.Black, fontSize = 54.sp, lineHeight = 58.sp, color = Orange)
        Spacer(Modifier.height(40.dp)); Text("مدیریت اختصاصی فروشگاه", fontWeight = FontWeight.Bold, fontSize = 22.sp)
        Text("ورود فقط برای مدیر اصلی مجاز است", color = Color.Gray)
        Spacer(Modifier.height(22.dp))
        OutlinedTextField(email, {email=it}, modifier=Modifier.fillMaxWidth(), label={Text("ایمیل مدیر")}, singleLine=true,
            keyboardOptions=KeyboardOptions(keyboardType=KeyboardType.Email))
        Spacer(Modifier.height(12.dp))
        OutlinedTextField(password, {password=it}, modifier=Modifier.fillMaxWidth(), label={Text("رمز عبور")}, singleLine=true, visualTransformation=PasswordVisualTransformation())
        Spacer(Modifier.height(22.dp))
        Button(onClick={onLogin(email,password)}, enabled=!busy&&email.isNotBlank()&&password.isNotBlank(),
            modifier=Modifier.fillMaxWidth().height(54.dp), shape=RoundedCornerShape(9.dp)) { Text("ورود به مدیریت") }
        if (message.isNotBlank()) Text(message, color=Orange)
    }
}

@Composable
private fun Dashboard(data: JSONObject, onProducts:()->Unit,onOrders:()->Unit,onRefresh:()->Unit) {
    Column(modifier=Modifier.fillMaxSize().padding(19.dp), verticalArrangement=Arrangement.spacedBy(13.dp)) {
        Text("داشبورد", fontSize=29.sp, fontWeight=FontWeight.Black)
        Text("همه‌چیز از همین‌جا مدیریت می‌شود.", color=Color.Gray, fontSize=12.sp)
        Spacer(Modifier.height(7.dp))
        Row(horizontalArrangement=Arrangement.spacedBy(10.dp)) {
            StatCard("محصولات فعال",data.optInt("products").toString(),Modifier.weight(1f))
            StatCard("کل سفارش‌ها",data.optInt("orders").toString(),Modifier.weight(1f))
        }
        Row(horizontalArrangement=Arrangement.spacedBy(10.dp)) {
            StatCard("کم‌موجودی",data.optInt("low_stock").toString(),Modifier.weight(1f))
            StatCard("سفارش تأییدشده",data.optLong("sales_total").toString()+" ریال",Modifier.weight(1f))
        }
        Spacer(Modifier.height(12.dp))
        Button(onClick=onProducts,modifier=Modifier.fillMaxWidth().height(52.dp)){Text("مدیریت و ثبت محصول  ↖")}
        OutlinedButton(onClick=onOrders,modifier=Modifier.fillMaxWidth().height(52.dp)){Text("سفارش‌های مشتریان")}
        TextButton(onClick=onRefresh){Text("به‌روزرسانی اطلاعات")}
    }
}

@Composable private fun StatCard(label:String, value:String, modifier:Modifier=Modifier) {
    Card(modifier=modifier,shape=RoundedCornerShape(14.dp),colors=CardDefaults.cardColors(containerColor=Color.White)) {
        Column(Modifier.padding(17.dp)) { Text(label,color=Color.Gray,fontSize=11.sp);Spacer(Modifier.height(14.dp));Text(value,fontSize=21.sp,fontWeight=FontWeight.Black) }
    }
}

private fun jsonObjects(arr:JSONArray) = (0 until arr.length()).map { arr.getJSONObject(it) }

@Composable
private fun ProductsPanel(data:JSONArray,onAdd:()->Unit,onEdit:(JSONObject)->Unit,onDelete:(Int)->Unit) {
    Column(Modifier.fillMaxSize().padding(18.dp)) {
        Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.SpaceBetween,verticalAlignment=Alignment.CenterVertically) {
            Text("محصولات",fontSize=25.sp,fontWeight=FontWeight.Black)
            Button(onClick=onAdd,shape=RoundedCornerShape(8.dp)){Text("+ محصول جدید")}
        }
        Spacer(Modifier.height(15.dp))
        if (data.length()==0) Text("هنوز محصولی ثبت نشده. اولین محصول را اضافه کن.",color=Color.Gray)
        LazyColumn(verticalArrangement=Arrangement.spacedBy(9.dp)) {
            items(jsonObjects(data),key={it.getInt("id")}) { p ->
                Card(colors=CardDefaults.cardColors(containerColor=Color.White),shape=RoundedCornerShape(12.dp)) {
                    Column(Modifier.fillMaxWidth().padding(15.dp)) {
                        Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.SpaceBetween) {
                            Text(p.getString("name"),fontWeight=FontWeight.Bold,modifier=Modifier.weight(1f))
                            Text("#${p.getInt("id")}",color=Orange)
                        }
                        Text("${p.optLong("price")} ریال   ·   موجودی: ${p.optInt("stock")}",fontSize=12.sp,color=Color.Gray)
                        Row {
                            TextButton(onClick={onEdit(p)}){Text("ویرایش")}
                            TextButton(onClick={onDelete(p.getInt("id"))}){Text("غیرفعال‌سازی",color=Orange)}
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun ProductEditor(original:JSONObject?,busy:Boolean,onBack:()->Unit,onSave:(JSONObject,List<Uri>)->Unit) {
    var name by remember(original) { mutableStateOf(original?.optString("name") ?: "") }
    var description by remember(original) { mutableStateOf(original?.optString("description") ?: "") }
    var category by remember(original) { mutableStateOf(original?.optString("category") ?: "") }
    var price by remember(original) { mutableStateOf(original?.optLong("price")?.toString() ?: "") }
    var stock by remember(original) { mutableStateOf(original?.optInt("stock")?.toString() ?: "") }
    var active by remember(original) { mutableStateOf(original?.optBoolean("active", true) ?: true) }
    val selectedImages= remember(original) { mutableStateListOf<Uri>() }
    val picker = rememberLauncherForActivityResult(ActivityResultContracts.PickMultipleVisualMedia(8)) { uris ->
        selectedImages.clear();selectedImages.addAll(uris.take(8 - (original?.optJSONArray("images")?.length()?:0)))
    }
    val valid = name.isNotBlank() && price.toLongOrNull()!=null && stock.toIntOrNull()!=null &&
        (price.toLongOrNull()?:-1)>=0 && (stock.toIntOrNull()?:-1)>=0
    Column(Modifier.fillMaxSize().padding(20.dp)) {
        Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.SpaceBetween) {
            Text(if(original==null)"محصول جدید" else "ویرایش محصول",fontSize=24.sp,fontWeight=FontWeight.Black)
            TextButton(onClick=onBack){Text("بازگشت")}
        }
        Spacer(Modifier.height(8.dp))
        LazyColumn(verticalArrangement=Arrangement.spacedBy(12.dp)) {
            item { OutlinedTextField(name,{name=it},modifier=Modifier.fillMaxWidth(),label={Text("نام محصول")},singleLine=true) }
            item { OutlinedTextField(description,{description=it},modifier=Modifier.fillMaxWidth(),label={Text("توضیحات")},minLines=2) }
            item { OutlinedTextField(category,{category=it},modifier=Modifier.fillMaxWidth(),label={Text("دسته‌بندی")},singleLine=true) }
            item { OutlinedTextField(price,{price=it},modifier=Modifier.fillMaxWidth(),label={Text("قیمت (ریال)")},keyboardOptions=KeyboardOptions(keyboardType=KeyboardType.Number),singleLine=true) }
            item { OutlinedTextField(stock,{stock=it},modifier=Modifier.fillMaxWidth(),label={Text("موجودی")},keyboardOptions=KeyboardOptions(keyboardType=KeyboardType.Number),singleLine=true) }
            item {
                OutlinedButton(onClick={picker.launch(PickVisualMediaRequest(ActivityResultContracts.PickVisualMedia.ImageOnly))}, modifier=Modifier.fillMaxWidth()) {
                    Text("انتخاب تصاویر محصول (حداکثر ۸ تصویر)")
                }
                Text("${selectedImages.size} تصویر جدید انتخاب شد",fontSize=11.sp,color=Color.Gray)
            }
            item {
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    Switch(checked = active, onCheckedChange = { active = it })
                    Text("نمایش در فروشگاه")
                }
            }
            item {
                Button(enabled=valid&&!busy,onClick={
                    val payload=JSONObject().put("name",name.trim()).put("description",description.trim())
                        .put("category", category.trim()).put("price", price.toLong()).put("active", active)
                    val requestedStock = stock.toInt()
                    val previousStock = original?.getInt("stock")
                    if (requestedStock != previousStock) {
                        payload.put("stock", requestedStock)
                        if (previousStock != null) payload.put("expected_stock", previousStock)
                    }
                    onSave(payload,selectedImages.toList())
                },modifier=Modifier.fillMaxWidth().height(52.dp)) { Text("ذخیره محصول") }
            }
        }
    }
}

@Composable
private fun OrdersPanel(data:JSONArray,onChange:(Int,String)->Unit) {
    Column(Modifier.fillMaxSize().padding(18.dp)) {
        Text("سفارش‌ها",fontSize=25.sp,fontWeight=FontWeight.Black)
        Spacer(Modifier.height(14.dp))
        if(data.length()==0)Text("سفارشی ثبت نشده",color=Color.Gray)
        LazyColumn(verticalArrangement=Arrangement.spacedBy(9.dp)) {
            items(jsonObjects(data),key={it.getInt("id")}) { o ->
                val status = o.getString("status")
                val next = when(status) {"new"->"confirmed";"confirmed"->"shipped";"shipped"->"delivered";else->null}
                val label = when(next) {"confirmed"->"تأیید سفارش";"shipped"->"تحویل به ارسال";"delivered"->"تحویل‌شده";else->""}
                Card(colors=CardDefaults.cardColors(containerColor=Color.White),shape=RoundedCornerShape(12.dp)) {
                    Column(Modifier.fillMaxWidth().padding(15.dp)) {
                        Text("سفارش #${o.getInt("id")}",fontWeight=FontWeight.Bold)
                        Text("${o.optString("full_name")} · ${o.optString("phone")}",fontSize=12.sp)
                        Text(o.optString("address"),fontSize=11.sp,color=Color.Gray)
                        Text("${o.optLong("total")} ریال · ${o.optString("status_label")}",color=Orange,fontSize=12.sp)
                        val details = o.optJSONArray("items") ?: JSONArray()
                        for (i in 0 until details.length()) {
                            val item = details.getJSONObject(i)
                            Text("${item.optString("name")} × ${item.optInt("quantity")}",fontSize=11.sp,color=Color.DarkGray)
                        }
                        Row(horizontalArrangement=Arrangement.spacedBy(5.dp)) {
                            if(next!=null)TextButton(onClick={onChange(o.getInt("id"),next)}){Text(label)}
                            if(status=="new"||status=="confirmed")TextButton(onClick={onChange(o.getInt("id"),"cancelled")}){Text("لغو و بازگشت موجودی")}
                        }
                    }
                }
            }
        }
    }
}

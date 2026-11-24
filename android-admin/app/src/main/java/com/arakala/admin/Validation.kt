package com.arakala.admin

internal fun parseNumber(raw:String):Long? {
    val value=raw.trim().map { char ->
        when(char) {
            in '۰'..'۹' -> ('0'.code+char.code-'۰'.code).toChar()
            in '٠'..'٩' -> ('0'.code+char.code-'٠'.code).toChar()
            else -> char
        }
    }.joinToString("")
    return if(value.isNotEmpty() && value.all { it in '0'..'9' }) value.toLongOrNull() else null
}

internal fun validProductInput(name:String,category:String,description:String,price:String,discount:String,stock:String,sku:String,barcode:String):Boolean {
    val p=parseNumber(price) ?: return false
    val st=parseNumber(stock) ?: return false
    val d=if(discount.isBlank()) null else parseNumber(discount) ?: return false
    return name.isNotBlank() && name.trim().length<=160 && category.trim().length<=80 &&
        description.trim().length<=2000 && sku.trim().length<=40 && barcode.trim().length<=40 &&
        p in 0L..10_000_000_000L && st in 0L..1_000_000L && (d==null || d<p)
}

internal fun imageSample(width:Int,height:Int):Int {
    require(width>0 && height>0)
    var sample=1
    val side=maxOf(width,height).toLong()
    while(side/sample>2800) sample*=2
    return sample
}

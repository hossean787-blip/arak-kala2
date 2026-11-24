package com.arakala.admin

import org.junit.Assert.*
import org.junit.Test

class ValidationTest {
    @Test fun normalizesPersianAndArabicDigits() {
        assertEquals(1234L,parseNumber("۱۲٣۴"))
        assertEquals(0L,parseNumber("0"))
        assertNull(parseNumber("-1"))
        assertNull(parseNumber("1,000"))
        assertNull(parseNumber("99999999999999999999999999"))
    }
    @Test fun enforcesBoundsAndDiscount() {
        fun valid(p:String,d:String,s:String)=validProductInput("کالا","","",p,d,s,"","")
        assertTrue(valid("۱۰۰۰","۹۰۰","۱"))
        assertTrue(valid("10000000000","","1000000"))
        assertFalse(valid("10000000001","","0"))
        assertFalse(valid("1000","1000","1"))
        assertFalse(valid("1000","bad","1"))
        assertFalse(valid("1000","","1000001"))
    }
    @Test fun samplesLargeImages() {
        assertEquals(1,imageSample(1400,700))
        assertEquals(2,imageSample(4000,3000))
        assertEquals(4,imageSample(10000,7000))
    }
    @Test fun checksTextLengths() {
        assertFalse(validProductInput("","","","100","","1","",""))
        assertFalse(validProductInput("x".repeat(161),"","","100","","1","",""))
        assertFalse(validProductInput("کالا","","","100","","1","x".repeat(41),""))
    }
}

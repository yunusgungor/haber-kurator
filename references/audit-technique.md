# Audit/Dogrulama Teknigi — terminal vs execute_code

> **Tarih:** 2026-05-11
> **Kaynak:** haber-kurator %100 sağlamlık oturumu
> **Durum:** Aktif kullanımda

---

## Teknik Ozet

Haber Kuratör plugin audit veya verification script'leri yazarken, `terminal` tool'u `execute_code`'dan **kesinlikle daha guvenilirdir**.

---

## Neden terminal?

| Sorun | terminal | execute_code |
|-------|----------|--------------|
| Unicode/encoding | `grep -q` → sorun yok | Smart quotes (`"`) SyntaxError verir |
| Tool output key | Sabit `{"output": ..., "exit_code": N}` | Bazen sadece `stdout`, `output` yok → KeyError |
| Regex case-sensitivity | `grep -qE` veya `grep -i` ile net | Python regex: case-sensitive by default |
| Pipeline kopması | `cmd && echo OK || echo FAIL` — zincir kopmaz | `sum(1 for _, s in results if s)` → tum elemanlar ayni formatta olmali |
| Satir sayisi | `wc -l < file` → tek satir sonuc | `int(r["output"].split()[0])` → parse hatasi riski |
| Cat/grep pipeline | `cat -v \| grep -n` — sorunsuz | Python subprocess → herseyi parse et |

---

## Dogru Pattern — terminal (TERCIH EDILEN)

### Basit kontrol
```bash
grep -q "State Machine" "$co" && echo OK || echo FAIL
```

### Satir sayisi
```bash
lines=$(wc -l < "$f" 2>/dev/null || echo 0)
[ "$lines" -ge 40 ] && echo PASS || echo FAIL
```

### Çoklu kontrol
```bash
for pat in "State Machine" "captured" "archived"; do
  grep -q "$pat" "$co" && echo "  OK: $pat" || echo "  FAIL: $pat"
done
```

### Dizin/dosya varlik kontrolu
```bash
test -f "$path" && echo EXISTS || echo MISSING
test -d "$path" && echo IS_DIR || echo NOT_DIR
```

### Sayma
```bash
count=$(find /path -type f | wc -l)
echo "Found: $count files"
```

---

## Yanlis Pattern — execute_code (KACINILAN)

```python
# YANLIS 1: Unicode smart quote SyntaxError
print("=== KALAN 2 "FALSE NEGATIVE" MANUEL KONTROL ===")
#                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ SyntaxError

# YANLIS 2: KeyError — output yoksa
r = terminal(f"grep -c '{pat}' {file}")
val = int(r["output"].strip())  # KeyError: 'output' not in dict

# YANLIS 3: Yanlis assumption — 0 her zaman FAIL degil
s = "PASS" if val > 0 else "FAIL"  # val=0 bazen normal

# YANLIS 4: Regex case-sensitive
cmd = f"grep -c '{pat}' {file}"  # pat buyuk/kucuk harf uyumsuz → 0

# YANLIS 5: Pipeline zinciri kopmasi
r = terminal("find ... | xargs wc -l | tail -1")
# xargs basarisiz olsa bile exit_code=0 donebilir
```

---

## Iyi execute_code Kullanimi

execute_code hala iyidir su durumlarda:
- Hesaplama (`int(a) + int(b)` gibi)
- String manipulasyonu
- Conditional logic (`if val >= threshold`)
- Data structure olusturma

Ama **file system kontrolleri ve shell komutlari** icin `terminal` kullan.

---

## Ozel Durumlar

### `sed` ile satir okuma
```bash
r = terminal(f"sed -n '{offset},{offset+10}p' {file}")
# satir offset/limit pagination — SKILL.md gibi buyuk dosyalarda kullanislı
```

### `cat -v` ile encoding gorme
```bash
r = terminal(f"cat -v {file} | grep -n 'Draft'")
# Smart quote vs ASCII quote farkini gosterir
```

### diff ile dosya karsilastirma
```bash
diff -rq "$dir1" "$dir2" && echo "IDENTICAL" || echo "DIFFER"
```

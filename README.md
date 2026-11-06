# อับดุล — ถามไรตอบได้

**Ctrl+V Hackathon (Devpost 31831) — Information Access / AI/ML / Web Development**

เว็บแชทที่ถามอะไรก็ได้ แล้วได้คำตอบเป็น**ภาษาไทยบ้านๆ** เข้าใจง่าย —
ไม่ต้องไปขุด Google เอง ไม่ต้องรู้ศัพท์ยาก

## วิธีใช้

1. พิมพ์คำถามอะไรก็ได้ เช่น “ดอกเบี้ยทบต้นคืออะไร” หรือ “เงินเฟ้อแปลว่าอะไร”
2. หรือกด **📄 แปะเอกสารแล้วถาม** วางข้อความจากจดหมาย สัญญา ใบแจ้งหนี้
   หรือบทความที่อ่านแล้วงง แล้วถามว่า “อันนี้คืออะไร”
3. อับดุลตอบสั้นๆ ตรงประเด็นก่อน แล้วค่อยขยายความถ้าต้องการ

## กฎของอับดุล (อยู่ใน system prompt ของเซิร์ฟเวอร์)

- ตอบเป็นภาษาไทยธรรมดาๆ ห้ามใช้ศัพท์ยากโดยไม่อธิบาย
- ถ้าไม่แน่ใจ บอกตรงๆ ว่าไม่แน่ใจ — แยกให้ชัดว่าอะไรมีหลักฐาน กับอะไรคือการเดา
- ห้ามแต่งเรื่อง ห้ามอ้างตัวเลข/วันที่/ชื่อที่จำไม่ได้
- ถามจากเอกสารที่แปะมา ตอบจากเอกสารนั้นเท่านั้น ถ้าในเอกสารไม่มีคำตอบก็บอกว่าไม่มี

## สถาปัตยกรรม

```
ผู้ใช้ -> https://abdul.sydear.space (nginx)
      -> abdul server (Python stdlib, :28100)
      -> SYDEAR Router Gateway (model alias: sydear-photon / MiniMax M3.1 Flash)
```

- **Frontend:** `public/index.html` — แชท UI อย่างเดียว ประวัติแชทเก็บใน
  localStorage ของเบราว์เซอร์ผู้ใช้
- **Backend:** `server.py` — Python stdlib ล้วน (ไม่มี dependency)
  เสิร์ฟไฟล์ static + proxy `POST /api/chat` ไปยัง gateway
- **API key ของ gateway อยู่บนเซิร์ฟเวอร์เท่านั้น** (ไฟล์ `.keys/abdul.key`
  โหมด 0600) — ไม่เคยอยู่ใน repo หรือโค้ดฝั่งเบราว์เซอร์
- Rate limit ง่ายๆ: 20 ครั้ง / 60 วินาที / IP (กันคนยิงเล่น)

## รันเอง (dev)

```bash
python3 server.py   # ฟังที่ 127.0.0.1:28100
```

ตัวแปรแวดล้อม: `ABDUL_PORT`, `ABDUL_GW_URL`, `ABDUL_GW_MODEL`,
`ABDUL_GW_KEY_FILE`

## Deploy (NexNodo box)

```bash
sudo cp abdul.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now abdul
sudo cp nginx-abdul.conf /etc/nginx/sites-enabled/abdul.sydear.space
sudo nginx -t && sudo systemctl reload nginx
```

DNS: `abdul.sydear.space` → box IP (Cloudflare, proxied), TLS ผ่าน certbot.

## สถานะ

ต้นแบบชิ้นแรก (prototype) — สร้างในหน้าต่าง build ของ Ctrl+V
6–10 พ.ย. 2026, ส่งก่อน 11 พ.ย. 05:00 น.

"""
Logika inti deteksi BTP: preprocessing gambar, OCR ensemble, dan matching
ke database. Dipindah dari app.py (versi Flask) TANPA mengubah algoritma
sama sekali -- cuma dilepas dari lapisan web supaya bisa dipakai ulang di
Streamlit (atau di mana pun) dan diproses full in-memory.

PENTING: proses_gambar() di bagian bawah TIDAK PERNAH menulis file ke disk.
Gambar didekode langsung dari bytes upload dengan cv2.imdecode, diproses
di RAM, lalu hasilnya dibuang begitu request selesai. Ini yang bikin
deployment gak pernah kepenuhan sama file upload numpuk.
"""

import re
import json
from collections import Counter
import os
import cv2
import numpy as np
import pytesseract
from rapidfuzz import fuzz

# Di Windows, tesseract.exe biasanya gak otomatis kedeteksi di PATH.
# Sesuaikan path ini kalau lokasi instalasi Tesseract di komputer lo beda.
if os.name == 'nt':
    default_path = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
    if os.path.exists(default_path):
        pytesseract.pytesseract.tesseract_cmd = default_path

# Ambang batas kualitas OCR. Kalau hasil di bawah ini, kita anggap fotonya
# kurang layak dibaca (ketutup jari, terlalu silau, dll) daripada memaksa
# mencocokkan teks sampah ke database BTP dan kasih hasil yang salah.
MIN_GOOD_WORDS = 8
MIN_AVG_CONFIDENCE = 45

# Minimal berapa dari sekian kandidat OCR (variasi threshold x PSM x
# full-image/MSER-crop) yang harus sepakat menemukan suatu bahan, sebelum
# bahan itu dianggap valid. Pengaman terhadap false positive dari 1
# kandidat threshold yang kebetulan menghasilkan teks acak.
MIN_VOTES = 2

# Rasio minimal token (kata) yang panjangnya >= 4 huruf, dari total token,
# yang harus dipunyai suatu kandidat teks SEBELUM dia boleh ikut voting.
MIN_RASIO_TOKEN_BERMAKNA = 0.3


def load_database(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as file:
            return json.load(file)
    except Exception as e:
        print(f"[ERROR] Gagal memuat database: {e}")
        return []


def auto_rotate_image(img):
    """Koreksi rotasi 90/180/270 pakai OSD Tesseract. Rotasi HANYA
    diterapkan kalau orientation confidence-nya di atas ambang tertentu."""
    MIN_ORIENTATION_CONFIDENCE = 2.0
    try:
        osd = pytesseract.image_to_osd(img)
        rotate_angle = int(re.search(r'(?<=Rotate: )\d+', osd).group(0))
        conf_match = re.search(r'(?<=Orientation confidence: )[\d.]+', osd)
        confidence = float(conf_match.group(0)) if conf_match else 0.0

        if confidence < MIN_ORIENTATION_CONFIDENCE:
            return img

        if rotate_angle == 90:
            return cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
        elif rotate_angle == 180:
            return cv2.rotate(img, cv2.ROTATE_180)
        elif rotate_angle == 270:
            return cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)
    except Exception as e:
        print(f"[INFO] Skip rotasi otomatis: {e}")
    return img


def resize_max(img, max_dim=1800):
    h, w = img.shape[:2]
    scale = max_dim / max(h, w)
    if scale < 1:
        img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    return img


def illumination_normalize(gray, sigma=25):
    bg = cv2.GaussianBlur(gray, (0, 0), sigmaX=sigma)
    return cv2.divide(gray, bg, scale=255)


def ocr_word_confidence(img, config):
    data = pytesseract.image_to_data(img, lang='ind+eng', config=config,
                                      output_type=pytesseract.Output.DICT)
    good = [int(c) for c, w in zip(data['conf'], data['text'])
            if str(c) != '-1' and int(c) > 40 and w.strip()]
    if not good:
        return 0, 0, 0
    avg_conf = sum(good) / len(good)
    score = avg_conf * len(good)
    return score, len(good), avg_conf


def _ocr_on_variants(gray, label_prefix):
    norm = illumination_normalize(gray)
    candidates = {
        'adaptive': cv2.adaptiveThreshold(
            norm, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 15
        ),
        'otsu': cv2.threshold(norm, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1],
    }
    best = {'score': -1, 'text': '', 'nwords': 0, 'avg_conf': 0, 'method': None}
    for name, th in candidates.items():
        for psm in (4, 6):
            config = rf'--oem 3 --psm {psm}'
            score, nwords, avg_conf = ocr_word_confidence(th, config)
            if score > best['score']:
                text = pytesseract.image_to_string(th, lang='ind+eng', config=config)
                best.update(score=score, text=text, nwords=nwords, avg_conf=avg_conf,
                            method=f'{label_prefix}{name}_psm{psm}')
    return best


def mser_text_region_crop(gray):
    mser = cv2.MSER_create()
    mser.setMinArea(20)
    mser.setMaxArea(2000)
    regions, _ = mser.detectRegions(gray)

    boxes = []
    for p in regions:
        x, y, bw, bh = cv2.boundingRect(p.reshape(-1, 1, 2))
        if 4 <= bh <= 40 and 2 <= bw <= 40 and bw < bh * 3:
            boxes.append((x, y, bw, bh))

    if len(boxes) < 40:
        return None

    ys = np.array([y + bh / 2 for x, y, bw, bh in boxes])
    xs = np.array([x for x, y, bw, bh in boxes])
    hist, edges = np.histogram(ys, bins=30)
    dense_bins = np.where(hist > hist.mean())[0]
    if len(dense_bins) == 0:
        return None

    y_min, y_max = edges[dense_bins.min()], edges[dense_bins.max() + 1]
    x_min, x_max = xs.min(), xs.max()
    pad = 15
    h, w = gray.shape
    y_min, y_max = max(0, int(y_min - pad)), min(h, int(y_max + pad))
    x_min, x_max = max(0, int(x_min - pad)), min(w, int(x_max + pad))
    return gray[y_min:y_max, x_min:x_max]


def smart_preprocess_and_ocr(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    best = _ocr_on_variants(gray, label_prefix='')

    crop = mser_text_region_crop(gray)
    if crop is not None and crop.size > 0:
        fallback = _ocr_on_variants(crop, label_prefix='mser_')
        if fallback['score'] > best['score']:
            best = fallback

    return best


def semua_kandidat_teks(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    sumber = [('full', gray)]
    crop = mser_text_region_crop(gray)
    if crop is not None and crop.size > 0:
        sumber.append(('mser', crop))

    kandidat = []
    for src_name, g in sumber:
        norm = illumination_normalize(g)
        variasi = {
            'adaptive': cv2.adaptiveThreshold(
                norm, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 15
            ),
            'otsu': cv2.threshold(norm, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1],
        }
        for th_name, th in variasi.items():
            for psm in (4, 6):
                config = rf'--oem 3 --psm {psm}'
                text = pytesseract.image_to_string(th, lang='ind+eng', config=config)
                kandidat.append((f'{src_name}_{th_name}_psm{psm}', text))
    return kandidat


def rasio_token_bermakna(teks):
    tokens = re.findall(r'[A-Za-z]+', teks)
    if not tokens:
        return 0.0
    token_panjang = [t for t in tokens if len(t) >= 4]
    return len(token_panjang) / len(tokens)


def cari_bahan_dengan_voting(img, database_btp, min_votes=MIN_VOTES):
    semua_kandidat = semua_kandidat_teks(img)

    kandidat_terpakai = []
    for nama_kandidat, teks in semua_kandidat:
        fokus = potong_teks_komposisi(teks)
        if rasio_token_bermakna(fokus) < MIN_RASIO_TOKEN_BERMAKNA:
            continue
        kandidat_terpakai.append((nama_kandidat, fokus))

    counter = Counter()
    detail_sumber = {}
    for nama_kandidat, fokus in kandidat_terpakai:
        bersih = bersihkan_tanda_baca(fokus)
        for item in cari_bahan_berbahaya(bersih, database_btp):
            counter[item['nama_bahan']] += 1
            detail_sumber.setdefault(item['nama_bahan'], []).append(nama_kandidat)

    total_kandidat_terpakai = len(kandidat_terpakai) or 1
    hasil_final = []
    for item in database_btp:
        nama = item['nama_id']
        jumlah_voting = counter.get(nama, 0)
        if jumlah_voting >= min_votes:
            hasil_final.append({
                'nama_bahan': nama,
                'golongan': item['golongan'],
                'ins': item['ins'],
                'skor': round(jumlah_voting / total_kandidat_terpakai * 100, 1),
                'metode': f'Konsensus {jumlah_voting}/{total_kandidat_terpakai} kandidat OCR (valid)',
                'risiko': item['keterangan_risiko']
            })
    return hasil_final


def potong_teks_komposisi(teks):
    tokens = list(re.finditer(r'[A-Za-z]+', teks))
    headers = ('komposisi', 'ingredients')
    best_idx = None
    for m in tokens:
        word = m.group().lower()
        for h in headers:
            if abs(len(word) - len(h)) > 3:
                continue
            skor = fuzz.ratio(word, h)
            if skor >= 60 and (best_idx is None or m.start() < best_idx):
                best_idx = m.start()
    return teks[best_idx:] if best_idx is not None else teks


def bersihkan_tanda_baca(teks):
    return re.sub(r'[^\w\s%]', ' ', teks)


def cari_bahan_berbahaya(teks_fokus, database_btp):
    bahan_ditemukan = []
    for item in database_btp:
        skor_tertinggi_item = 0
        metode_tertinggi_item = ""
        threshold_final = 0

        for keyword in item["keyword_pencarian"]:
            skor_token = fuzz.token_set_ratio(keyword.lower(), teks_fokus.lower())
            skor_partial = fuzz.partial_ratio(keyword.lower(), teks_fokus.lower())

            panjang_keyword = len(keyword)

            if panjang_keyword <= 4:
                # REVISI: Perketat threshold mutlak buat BHA/BHT dll 
                if skor_token > skor_partial:
                    skor_saat_ini = skor_token
                    threshold_saat_ini = 95
                    metode_saat_ini = "Token Set"
                else:
                    skor_saat_ini = skor_partial
                    threshold_saat_ini = 100  # Mutlak
                    metode_saat_ini = "Partial (Strict)"
            elif panjang_keyword <= 12:
                skor_saat_ini = max(skor_token, skor_partial)
                threshold_saat_ini = 85
                metode_saat_ini = "Token Set" if skor_token > skor_partial else "Partial"
            else:
                skor_saat_ini = max(skor_token, skor_partial)
                threshold_saat_ini = 80
                metode_saat_ini = "Token Set" if skor_token > skor_partial else "Partial"

            if skor_saat_ini > skor_tertinggi_item:
                skor_tertinggi_item = skor_saat_ini
                metode_tertinggi_item = metode_saat_ini
                threshold_final = threshold_saat_ini

        if skor_tertinggi_item >= threshold_final:
            bahan_ditemukan.append({
                "nama_bahan": item["nama_id"],
                "golongan": item["golongan"],
                "ins": item["ins"],
                "skor": skor_tertinggi_item,
                "metode": metode_tertinggi_item,
                "risiko": item["keterangan_risiko"]
            })
    return bahan_ditemukan


def proses_gambar(image_bytes, database_btp):
    """Titik masuk utama untuk Streamlit: terima bytes gambar (dari
    st.camera_input / st.file_uploader), proses SELURUHNYA di memory
    (tidak pernah ditulis ke disk), lalu balikin dict hasil dengan bentuk
    yang sama seperti response JSON /scan di versi Flask.
    """
    file_bytes = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)

    if img is None:
        return {
            'success': False,
            'low_quality': True,
            'message': 'File gambar tidak dapat dibaca. Coba unggah ulang dengan format JPG/PNG/WEBP.',
            'teks_raw': '', 'teks_fokus': '', 'ocr_meta': {}, 'findings': []
        }

    # 1. Turunkan resolusi ke ukuran kerja yang wajar buat Tesseract
    img = resize_max(img, 1800)

    # 2. Rotasi otomatis (kelipatan 90 derajat) -- hasilnya tetap di RAM,
    # tidak ditulis ke disk.
    img_fixed = auto_rotate_image(img)

    # 3. Preprocessing + OCR ensemble, pilih kandidat terbaik otomatis
    hasil_ocr = smart_preprocess_and_ocr(img_fixed)
    teks_raw = hasil_ocr['text']

    # 4. Kalau kualitas OCR terlalu rendah, jangan paksa cocokkan ke database
    if hasil_ocr['nwords'] < MIN_GOOD_WORDS or hasil_ocr['avg_conf'] < MIN_AVG_CONFIDENCE:
        return {
            'success': False,
            'low_quality': True,
            'message': (
                'Foto komposisi kurang jelas terbaca (kemungkinan tertutup jari, '
                'silau/pantulan cahaya, atau blur). Coba foto ulang lebih dekat, '
                'tanpa jari menutupi teks, dan hindari sudut yang memantulkan cahaya.'
            ),
            'teks_raw': teks_raw,
            'ocr_meta': {'metode': hasil_ocr['method'], 'jumlah_kata_valid': hasil_ocr['nwords'],
                         'rata_rata_confidence': round(hasil_ocr['avg_conf'], 1)},
            'findings': []
        }

    # 5. Potong fokus ke bagian komposisi
    teks_fokus = potong_teks_komposisi(teks_raw)

    # 6. Cocokkan ke database BTP pakai voting dari SEMUA kandidat OCR
    bahan_ditemukan = cari_bahan_dengan_voting(img_fixed, database_btp)

    return {
        'success': True,
        'low_quality': False,
        'teks_raw': teks_raw,
        'teks_fokus': teks_fokus,
        'ocr_meta': {'metode': hasil_ocr['method'], 'jumlah_kata_valid': hasil_ocr['nwords'],
                     'rata_rata_confidence': round(hasil_ocr['avg_conf'], 1)},
        'findings': bahan_ditemukan
    }
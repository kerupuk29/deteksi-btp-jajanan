import cv2
import numpy as np
import pytesseract
from rapidfuzz import fuzz
import json
import re
import math
import os
from collections import Counter

# --- PATH TESSERACT (WAJIB UNTUK WINDOWS) ---
# Jika instalasi lu beda (misal di drive D atau AppData), ubah path ini
if os.name == 'nt':
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# --- IMPORT KAMUS BARU ---
try:
    from kamus_id_domain import SEMUA_KATA_DOMAIN
except ImportError:
    SEMUA_KATA_DOMAIN = set()

# --- AMBANG BATAS (THRESHOLDS) ---
MIN_GOOD_WORDS = 15
MIN_AVG_CONFIDENCE = 50.0
MIN_RASIO_KAMUS = 0.277  # Ambang batas ketat dari hasil evaluasi
MIN_VOTES = 1

def rasio_kata_valid_kamus(teks, min_panjang=3):
    """Menghitung rasio kata yang ada di kamus untuk mendeteksi halusinasi OCR."""
    tokens = [t.lower() for t in re.findall(r'[A-Za-z]+', teks) if len(t) >= min_panjang]
    if not tokens:
        return 0.0
    if not SEMUA_KATA_DOMAIN: 
        return 1.0 # Bypass jika kamus gagal dimuat
    valid = [t for t in tokens if t in SEMUA_KATA_DOMAIN]
    return len(valid) / len(tokens)

def validasi_kualitas_teks(teks_fokus, nwords, avg_conf):
    """Fungsi gatekeeper untuk menolak gambar yang gagal diekstrak OCR."""
    if nwords < MIN_GOOD_WORDS or avg_conf < MIN_AVG_CONFIDENCE:
        return False, "Kualitas teks terlalu rendah. Pastikan foto fokus dan tidak blur."
        
    if len(teks_fokus.strip()) < 15:
        return False, "Teks yang terbaca terlalu pendek. Pastikan permukaan kemasan rata."

    rasio_kamus = rasio_kata_valid_kamus(teks_fokus)
    print(f"[DEBUG] Rasio Kamus: {rasio_kamus:.3f} (Min: {MIN_RASIO_KAMUS})") 
    
    if rasio_kamus < MIN_RASIO_KAMUS:
        return False, "Banyak teks tidak bermakna (kemungkinan terdistorsi kelengkungan/cahaya). Silakan foto ulang pada area yang rata."

    return True, "Aman diproses"

def load_database(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as file:
            return json.load(file)
    except Exception as e:
        print(f"[ERROR] Gagal memuat database: {e}")
        return []

def auto_rotate_image(img):
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
        pass
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
    data = pytesseract.image_to_data(img, lang='ind+eng', config=config, output_type=pytesseract.Output.DICT)
    good = [int(c) for c, w in zip(data['conf'], data['text']) if str(c) != '-1' and int(c) > 40 and w.strip()]
    if not good:
        return 0, 0, 0
    avg_conf = sum(good) / len(good)
    score = avg_conf * len(good)
    return score, len(good), avg_conf

def _ocr_on_variants(gray, label_prefix):
    norm = illumination_normalize(gray)
    candidates = {
        'adaptive': cv2.adaptiveThreshold(norm, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 15),
        'otsu': cv2.threshold(norm, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1],
    }
    best = {'score': -1, 'text': '', 'nwords': 0, 'avg_conf': 0, 'method': None}
    for name, th in candidates.items():
        for psm in (4, 6):
            config = rf'--oem 3 --psm {psm}'
            score, nwords, avg_conf = ocr_word_confidence(th, config)
            if score > best['score']:
                text = pytesseract.image_to_string(th, lang='ind+eng', config=config)
                best.update(score=score, text=text, nwords=nwords, avg_conf=avg_conf, method=f'{label_prefix}{name}_psm{psm}')
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
            'adaptive': cv2.adaptiveThreshold(norm, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 15),
            'otsu': cv2.threshold(norm, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1],
        }
        for th_name, th in variasi.items():
            for psm in (4, 6):
                config = rf'--oem 3 --psm {psm}'
                text = pytesseract.image_to_string(th, lang='ind+eng', config=config)
                kandidat.append((f'{src_name}_{th_name}_psm{psm}', text))
    return kandidat

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
                if skor_token > skor_partial:
                    skor_saat_ini, threshold_saat_ini, metode_saat_ini = skor_token, 95, "Token Set"
                else:
                    skor_saat_ini, threshold_saat_ini, metode_saat_ini = skor_partial, 100, "Partial (Strict)"
            elif panjang_keyword <= 12:
                skor_saat_ini, threshold_saat_ini, metode_saat_ini = max(skor_token, skor_partial), 85, "Token Set" if skor_token > skor_partial else "Partial"
            else:
                skor_saat_ini, threshold_saat_ini, metode_saat_ini = max(skor_token, skor_partial), 80, "Token Set" if skor_token > skor_partial else "Partial"

            if skor_saat_ini > skor_tertinggi_item:
                skor_tertinggi_item, metode_tertinggi_item, threshold_final = skor_saat_ini, metode_saat_ini, threshold_saat_ini

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

def cari_bahan_dengan_voting(img, database_btp, min_votes=MIN_VOTES):
    semua_kandidat = semua_kandidat_teks(img)
    kandidat_terpakai = []
    
    for nama_kandidat, teks in semua_kandidat:
        fokus = potong_teks_komposisi(teks)
        # Menggunakan metrik kamus baru untuk filter kandidat jelek
        if rasio_kata_valid_kamus(fokus) < MIN_RASIO_KAMUS:
            continue
        kandidat_terpakai.append((nama_kandidat, fokus))

    counter = Counter()
    for nama_kandidat, fokus in kandidat_terpakai:
        bersih = bersihkan_tanda_baca(fokus)
        for item in cari_bahan_berbahaya(bersih, database_btp):
            counter[item['nama_bahan']] += 1

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
                'metode': f'Konsensus {jumlah_voting}/{total_kandidat_terpakai} kandidat OCR',
                'risiko': item['keterangan_risiko']
            })
    return hasil_final

def proses_gambar(image_bytes, database_btp):
    file_bytes = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)

    if img is None:
        return {
            'success': False, 'low_quality': True,
            'message': 'File gambar tidak dapat dibaca. Coba unggah ulang format JPG/PNG/WEBP.',
            'teks_raw': '', 'teks_fokus': '', 'ocr_meta': {}, 'findings': []
        }

    img = resize_max(img, 1800)
    img_fixed = auto_rotate_image(img)
    
    hasil_ocr = smart_preprocess_and_ocr(img_fixed)
    teks_raw = hasil_ocr['text']
    teks_fokus = potong_teks_komposisi(teks_raw)

    # GATEKEEPER BERBASIS KAMUS DIEKSEKUSI DI SINI
    is_valid, pesan = validasi_kualitas_teks(teks_fokus, hasil_ocr['nwords'], hasil_ocr['avg_conf'])
    if not is_valid:
        return {
            'success': False,
            'low_quality': True,
            'message': pesan,
            'teks_raw': teks_raw,
            'teks_fokus': teks_fokus,
            'ocr_meta': {'metode': hasil_ocr.get('method', ''), 'jumlah_kata_valid': hasil_ocr['nwords'], 'rata_rata_confidence': round(hasil_ocr['avg_conf'], 1)},
            'findings': []
        }

    bahan_ditemukan = cari_bahan_dengan_voting(img_fixed, database_btp)

    return {
        'success': True,
        'low_quality': False,
        'teks_raw': teks_raw,
        'teks_fokus': teks_fokus,
        'ocr_meta': {'metode': hasil_ocr.get('method', ''), 'jumlah_kata_valid': hasil_ocr['nwords'], 'rata_rata_confidence': round(hasil_ocr['avg_conf'], 1)},
        'findings': bahan_ditemukan
    }

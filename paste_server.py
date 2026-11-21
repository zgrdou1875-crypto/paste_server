import os
from flask import Flask, request, render_template_string, redirect, url_for, session, send_from_directory

app = Flask(__name__)
app.secret_key = 'dhksddosifoidjkladskfadsf'

# 设置访问密码（留空则不开启密码验证）
ACCESS_PASSWORD = "1518"

# 上传文件存储路径与允许格式
UPLOAD_FOLDER = '/var/www/clipboard/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# 全局内存变量
clipboard_text = ""
current_image = None  # 记录当前图片文件名

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
    <title>云端剪贴板</title>
    <script src="https://cdn.jsdelivr.net/npm/qrcodejs@1.0.0/qrcode.min.js"></script>
    <style>
        body { font-family: -apple-system, sans-serif; padding: 20px; background: #f4f4f9; max-width: 500px; margin: 0 auto; }
        textarea, input[type="password"] { width: 100%; font-size: 16px; border-radius: 8px; border: 1px solid #ccc; padding: 10px; box-sizing: border-box; }
        textarea { height: 130px; resize: vertical; }
        
        .card { background: #fff; padding: 15px; border-radius: 12px; margin-bottom: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); }
        .card-title { font-size: 16px; font-weight: bold; margin-bottom: 10px; color: #333; }
        
        .btn-group { display: flex; gap: 8px; margin-top: 10px; }
        button, .file-label, .btn-link { flex: 1; padding: 12px; color: white; border: none; border-radius: 8px; font-size: 15px; font-weight: bold; cursor: pointer; text-align: center; text-decoration: none; display: inline-block; box-sizing: border-box; }
        .btn-submit { background: #007aff; }
        .btn-copy { background: #34c759; }
        .btn-refresh { background: #8e8e93; }
        .btn-download { background: #5856d6; }
        .btn-clear { background: #ff3b30; }
        
        /* 图片区域样式 */
        .img-preview { max-width: 100%; border-radius: 8px; margin-top: 10px; display: block; }
        .file-input { display: none; }
        
        .toast { visibility: hidden; min-width: 150px; background-color: #333; color: #fff; text-align: center; border-radius: 6px; padding: 10px; position: fixed; z-index: 99; bottom: 30px; left: 50%; transform: translateX(-50%); font-size: 14px; opacity: 0; transition: opacity 0.3s; }
        .toast.show { visibility: visible; opacity: 1; }
        
        .qr-card { text-align: center; }
        .qr-title { font-size: 14px; color: #666; margin-bottom: 12px; }
        #qrcode { display: inline-block; padding: 8px; background: #fff; }
        #qrcode img { margin: 0 auto; }
    </style>
</head>
<body>
    {% if not logged_in %}
    <div class="card">
        <div class="card-title">🔒 请输入访问密码</div>
        <form method="POST" action="/login">
            <input type="password" name="password" placeholder="密码" required>
            <button type="submit" class="btn-submit" style="margin-top:10px; width:100%;">登录</button>
        </form>
    </div>
    {% else %}
    
    <!-- 1. 文本传输区 -->
    <div class="card">
        <div class="card-title">📋 文本传输</div>
        <!-- 禁用浏览器自动填充与记忆 -->
        <form id="text-form" autocomplete="off">
            <textarea id="text-input" name="text" placeholder="在此输入或粘贴文字..." autocomplete="off">{{ text }}</textarea>
            <div class="btn-group">
                <button type="button" class="btn-submit" onclick="submitText()">更新发送</button>
                <button type="button" class="btn-copy" onclick="copyText()">一键复制</button>
                <button type="button" class="btn-refresh" onclick="location.reload()">刷新</button>
            </div>
        </form>
    </div>

    <!-- 2. 图片传输区 -->
    <div class="card">
        <div class="card-title">🖼️ 图片传输</div>
        <form id="upload-form" action="/upload" method="POST" enctype="multipart/form-data">
            <label for="image-upload" class="file-label btn-submit" style="width:100%;">选择/粘贴图片上传</label>
            <input id="image-upload" class="file-input" type="file" name="file" accept="image/*" onchange="document.getElementById('upload-form').submit()">
        </form>

        {% if image %}
        <div style="margin-top: 15px;">
            <img src="/uploads/{{ image }}" class="img-preview" alt="云端图片">
            <div class="btn-group" style="margin-top: 10px;">
                <a href="/uploads/{{ image }}" download class="btn-download btn-link">下载原图</a>
                <form action="/clear_image" method="POST" style="flex:1;">
                    <button type="submit" class="btn-clear" style="width:100%;">清空图片</button>
                </form>
            </div>
        </div>
        {% else %}
        <p style="color: #8e8e93; font-size: 14px; margin-top: 10px; text-align: center;">暂无上传的图片</p>
        {% endif %}
    </div>

    <!-- 3. 二维码卡片 -->
    <div class="card qr-card">
        <div class="qr-title">📱 扫码在手机打开此页面</div>
        <div id="qrcode"></div>
    </div>
    {% endif %}

    <div id="toast" class="toast">复制成功！</div>

    <script>
        // Ajax 异步提交文本函数，防止浏览器回弹旧数据
        function submitText() {
            var textValue = document.getElementById("text-input").value;
            fetch('/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                },
                body: 'text=' + encodeURIComponent(textValue)
            })
            .then(response => {
                if (response.ok) {
                    showToast("发送成功！");
                    // 同样自动清理掉当前界面显示的图片预览（跟后端的清空操作同步）
                    var imgCard = document.querySelector('.img-preview');
                    if (imgCard) {
                        location.reload();
                    }
                } else {
                    showToast("发送失败，请重试");
                }
            })
            .catch(error => {
                showToast("网络错误");
            });
        }

        function copyText() {
            var textarea = document.getElementById("text-input");
            if (!textarea || !textarea.value) { showToast("没有可复制的内容！"); return; }
            if (navigator.clipboard && window.isSecureContext) {
                navigator.clipboard.writeText(textarea.value).then(() => showToast("复制成功！")).catch(() => fallbackCopy(textarea));
            } else { fallbackCopy(textarea); }
        }
        function fallbackCopy(textarea) {
            textarea.select();
            textarea.setSelectionRange(0, 99999);
            try {
                if (document.execCommand('copy')) showToast("复制成功！");
                else showToast("复制失败");
            } catch (err) { showToast("复制失败"); }
        }
        function showToast(msg) {
            var toast = document.getElementById("toast");
            toast.innerText = msg; toast.className = "toast show";
            setTimeout(() => { toast.className = toast.className.replace("show", ""); }, 2000);
        }

        {% if logged_in %}
        window.onload = function() {
            var currentUrl = window.location.href;
            new QRCode(document.getElementById("qrcode"), {
                text: currentUrl,
                width: 140,
                height: 140,
                colorDark : "#000000",
                colorLight : "#ffffff",
                correctLevel : QRCode.CorrectLevel.M
            });
        };

        // 支持 Ctrl+V 粘贴图片上传
        document.addEventListener('paste', function (event) {
            var items = (event.clipboardData || event.originalEvent.clipboardData).items;
            for (var index in items) {
                var item = items[index];
                if (item.kind === 'file' && item.type.indexOf('image') !== -1) {
                    var blob = item.getAsFile();
                    var formData = new FormData();
                    formData.append('file', blob, 'pasted_image.png');

                    showToast("正在上传图片...");
                    fetch('/upload', {
                        method: 'POST',
                        body: formData
                    }).then(response => {
                        if (response.redirected) {
                            window.location.href = response.url;
                        } else {
                            location.reload();
                        }
                    });
                }
            }
        });
        {% endif %}
    </script>
</body>
</html>
"""

@app.route('/', methods=['GET', 'POST'])
def index():
    global clipboard_text, current_image
    if ACCESS_PASSWORD and not session.get('authenticated'):
        return render_template_string(HTML_TEMPLATE, logged_in=False, text="", image=None)
    
    if request.method == 'POST':
        clipboard_text = request.form.get('text', '')
        current_image = None  # 发送新文本时同步清空旧图片
        return "OK", 200     # 返回 200 给 Ajax 确认，不再重定向刷新页面
        
    return render_template_string(HTML_TEMPLATE, logged_in=True, text=clipboard_text, image=current_image)

@app.route('/upload', methods=['POST'])
def upload_file():
    global current_image
    if ACCESS_PASSWORD and not session.get('authenticated'):
        return redirect(url_for('index'))
        
    if 'file' not in request.files:
        return redirect(url_for('index'))
    file = request.files['file']
    if file.filename == '':
        return redirect(url_for('index'))
        
    if file and allowed_file(file.filename):
        filename = f"image_{os.urandom(4).hex()}" + os.path.splitext(file.filename)[1].lower()
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        current_image = filename
        
    return redirect(url_for('index'))

@app.route('/clear_image', methods=['POST'])
def clear_image():
    global current_image
    if ACCESS_PASSWORD and not session.get('authenticated'):
        return redirect(url_for('index'))
    
    current_image = None
    return redirect(url_for('index'))

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    if ACCESS_PASSWORD and not session.get('authenticated'):
        return "Unauthorized", 401
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/login', methods=['POST'])
def login():
    if request.form.get('password') == ACCESS_PASSWORD:
        session['authenticated'] = True
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000)


# 生成 tabBar 图标
from PIL import Image, ImageDraw
import os

output_dir = 'D:/code/ai_image_miniprogram/miniprogram/images'
os.makedirs(output_dir, exist_ok=True)
size = 81
gray = '#666666'
black = '#111111'

# ===== home 图标（矩形+三角形屋顶）=====
for color, suffix in [(gray, '.png'), (black, '-active.png')]:
    img = Image.new('RGBA', (size, size), (0,0,0,0))
    draw = ImageDraw.Draw(img)
    # 房子主体
    draw.rectangle([20, 35, 61, 71], fill=color)
    # 屋顶三角形
    draw.polygon([(20,35), (61,35), (40,20)], fill=color)
    img.save(os.path.join(output_dir, f'home{suffix}'))
    print(f'Created home{suffix}')

# ===== user 图标（圆形头像）=====
for color, suffix in [(gray, '.png'), (black, '-active.png')]:
    img = Image.new('RGBA', (size, size), (0,0,0,0))
    draw = ImageDraw.Draw(img)
    # 头部
    draw.ellipse([25, 14, 56, 45], fill=color)
    # 身体
    draw.ellipse([18, 38, 63, 68], fill=color)
    img.save(os.path.join(output_dir, f'user{suffix}'))
    print(f'Created user{suffix}')

print('All icons generated.')

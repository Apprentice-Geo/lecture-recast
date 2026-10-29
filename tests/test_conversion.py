import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from fetch_article import convert_article, reading_minutes, markdown_destination


class ConversionTests(unittest.TestCase):
    def convert(self, fragment, download=lambda url, name: None):
        return convert_article(f'<nav>不要抓取导航</nav><div class="wiki"><h1>测试文章</h1>{fragment}</div>',
                               "https://jyywiki.cn/GSE/2026/lect5.md", "测试文章", download)

    def test_structure_code_links_and_table(self):
        md, *_ = self.convert('<h2>小节</h2><p>原文<strong>强调</strong>和<a href="../">来源</a>。</p>'
                              '<pre><code class="language-python">x = "```"\nif x &lt; y:\n    a_b = 1\n</code></pre>'
                              '<ul><li>甲</li><li>乙</li></ul><table><tr><th>列</th></tr><tr><td>值</td></tr></table>')
        self.assertIn('## 小节', md)
        self.assertIn('原文**强调**和[来源](https://jyywiki.cn/GSE/)。', md)
        self.assertIn('````python\nx = "```"\nif x < y:\n    a_b = 1\n````', md)
        self.assertIn('- 甲\n- 乙', md)
        self.assertIn('| 列 |', md)
        self.assertIn('| 值 |', md)
        self.assertNotIn('不要抓取导航', md)

    def test_images_are_shared_local_paths_with_unique_filenames(self):
        downloaded = []
        md, _, _, images, _ = self.convert('<p><img src="/a/图.png?v=1" alt="图示">'
                                            '<img src="/a/图.png?v=1"><img src="/b/图.png?v=2"></p>',
                                            lambda url, name: downloaded.append((url, name)))
        self.assertEqual(len(downloaded), 2)
        self.assertEqual(len(images), 2)
        self.assertNotEqual(downloaded[0][1], downloaded[1][1])
        self.assertIn(f'![图示](../Assets/测试文章/{downloaded[0][1]})', md)
        self.assertEqual(md.count('../Assets/测试文章/'), 3)

    def test_nested_image_remains_an_image(self):
        md, *_ = self.convert('<p><a href="/original"><span><img alt="嵌套图" src="/image.png"></span></a></p>')
        self.assertIn('![嵌套图](../Assets/测试文章/', md)

    def test_katex_and_mathjax_keep_tex_once(self):
        md, *_ = self.convert(r'<p>行内 <span class="katex"><span>重复显示内容</span><annotation encoding="application/x-tex">x_i^2</annotation></span>。</p>'
                              r'<span class="katex-display"><span class="katex"><annotation encoding="application/x-tex">\frac{a_b}{c}</annotation></span></span>'
                              r'<p>还有 \(a_b\) 和 $q_r$。</p><p>\[x_y = 1\]</p>'
                              r'<script type="math/tex; mode=display">s_t=2</script>'
                              r'<pre><code>\(code_only\) $$literal$$</code></pre>')
        self.assertIn('$x_i^2$', md)
        self.assertEqual(md.count(r'\frac{a_b}{c}'), 1)
        self.assertIn('$$\n' + r'\frac{a_b}{c}' + '\n$$', md)
        self.assertIn('$a_b$', md)
        self.assertIn('$q_r$', md)
        self.assertIn('$$\nx_y = 1\n$$', md)
        self.assertIn('$$\ns_t=2\n$$', md)
        self.assertIn(r'\(code_only\) $$literal$$', md)
        self.assertNotIn('重复显示内容', md)
        self.assertNotIn('LECTUREMATHTOKEN', md)

    def test_unrecognized_body_fails_instead_of_converting_navigation(self):
        with self.assertRaisesRegex(ValueError, '正文'):
            convert_article('<h1>错误页面</h1>', 'https://example.com/', '测试', lambda *args: None)

    def test_reading_time_is_at_least_one_and_counts_mixed_language(self):
        self.assertEqual(reading_minutes(''), (1, 0))
        self.assertEqual(reading_minutes('中文 hello world'), (1, 4))

    def test_destination_with_spaces_or_parentheses_remains_valid_markdown(self):
        self.assertEqual(markdown_destination('../Assets/版本管理 (1)/cover.png'),
                         '<../Assets/版本管理 (1)/cover.png>')

    def test_download_failure_is_not_silently_dropped(self):
        def fail(*args):
            raise OSError('下载失败')
        with self.assertRaisesRegex(OSError, '下载失败'):
            self.convert('<img src="/a.png">', fail)


if __name__ == '__main__':
    unittest.main()

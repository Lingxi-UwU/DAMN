"""Concise Chinese purposes; source descriptions and detailed evidence stay separate."""
import re
SUMMARY_REVISION=1
PREFIX=r'^(?:(?:网页|页面|平台|官网|项目|资料|来源)(?:上)?(?:的)?(?:描述|介绍|说明|显示|称)(?:为|是|该模组|这个模组|：|:)?|根据(?:网页|页面|平台|官网|已取得的资料|资料)(?:描述|介绍|说明|显示)?[，,：:]?|该模组(?:主要)?(?:用于|可以)|这是一个)\s*'
def clean_purpose(value):
 if not isinstance(value,str):return ''
 text=re.sub(r'\s+',' ',value).strip()
 if not re.search(r'[\u4e00-\u9fff]',text):return ''
 for _ in range(3):text=re.sub(PREFIX,'',text).strip(' ：:，,')
 text=re.split(r'(?:本地(?:文件)?(?:声明|要求)|(?:需要|要求)(?:安装|使用)?\s*(?:NeoForge|Forge|Fabric|Minecraft)|(?:兼容|支持|适用)(?:的)?(?:游戏)?版本[：:])',text,maxsplit=1)[0].strip(' ，,；;')
 # A migration/version paragraph does not say what the player can do.
 if re.search(r'完整移植|维护分叉|保留原内容|移植(?:版|分支)',text) or re.search(r'\d+(?:\.\d+){1,}',text):return ''
 if not text or re.search(r'^(文件没有提供|仅有下载清单|尚未读取|暂无|No description|清单未提供|资料不足|无法确认)',text,re.I):return ''
 sentences=re.split(r'(?<=[。！？])',text);text=sentences[0].strip()
 han=len(re.findall(r'[\u4e00-\u9fff]',text));latin=len(re.findall(r'[A-Za-z]',text))
 if not han or latin>8*han+30 or len(text)>100:return ''
 return text if text[-1:] in '。！？' else text+'。'
def local_description(mod):
 text=mod.get('originalDescription') or mod.get('description') or ''
 return text.strip() if isinstance(text,str) and len(text.strip())>=5 and not re.match(r'^(文件没有提供|仅有下载清单|尚未读取|暂无|No description|清单未提供)',text,re.I) else ''
def annotation_purpose(annotation):
 return clean_purpose((annotation or {}).get('purpose')) or clean_purpose((annotation or {}).get('summary'))

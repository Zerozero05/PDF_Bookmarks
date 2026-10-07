"""Public GitHub release checks; no credential is stored or sent by the app."""

from dataclasses import dataclass
import json
import re
import urllib.error
import urllib.parse
import urllib.request

from .manifest import validate_release_manifest


REPOSITORY = "Zerozero05/PDF_Bookmarks"
RELEASE_API = f"https://api.github.com/repos/{REPOSITORY}/releases/latest"
MAX_JSON_BYTES = 2 * 1024 * 1024


class UpdateCheckError(ValueError):
    """The release cannot be safely interpreted or reached."""


@dataclass(frozen=True)
class UpdateOffer:
    version: str
    manifest: dict
    asset: dict
    release_notes: str
    release_url: str


def trusted_https(url):
    try:
        if not isinstance(url, str) or not url or any(char.isspace() or ord(char) < 32 for char in url):
            raise ValueError("invalid URL")
        parsed = urllib.parse.urlsplit(url)
        host = (parsed.hostname or "").lower()
        allowed = (parsed.scheme == "https" and parsed.username is None and parsed.password is None
                   and parsed.port in (None, 443) and not parsed.fragment
                   and (host in {"github.com", "api.github.com"}
                        or host.endswith(".githubusercontent.com")))
    except ValueError:
        allowed = False
    if not allowed:
        raise UpdateCheckError("更新地址必须是 GitHub 的 HTTPS 地址。")
    return url


class GitHubRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Reject a redirect before making a request to its destination."""

    def redirect_request(self, request, file, code, message, headers, new_url):
        trusted_https(new_url)
        return super().redirect_request(request, file, code, message, headers, new_url)


def open_github(request, timeout):
    return urllib.request.build_opener(GitHubRedirectHandler()).open(request, timeout=timeout)


def _invalid_json_constant(value):
    raise UpdateCheckError(f"更新清单含非 JSON 数值：{value}")


def version_key(value):
    if not isinstance(value, str) or not re.fullmatch(r"(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)", value):
        raise UpdateCheckError("正式版版本号无效，不能安全自动更新。")
    return tuple(map(int, value.split(".")))


def read_json(url, *, opener=None):
    trusted_https(url)
    request = urllib.request.Request(url, headers={
        "User-Agent": "PDF_Bookmarks-Updater",
        "Accept": "application/vnd.github+json" if urllib.parse.urlsplit(url).hostname == "api.github.com" else "application/json",
    })
    opener = opener or open_github
    try:
        with opener(request, timeout=20) as response:
            trusted_https(response.geturl())
            raw = response.read(MAX_JSON_BYTES + 1)
        if len(raw) > MAX_JSON_BYTES:
            raise UpdateCheckError("更新清单过大，请通过发布页手动更新。")
        result = json.loads(raw.decode("utf-8-sig"), parse_constant=_invalid_json_constant)
        if not isinstance(result, dict):
            raise UpdateCheckError("更新清单必须是 JSON 对象。")
        return result
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise UpdateCheckError(f"无法获取更新信息：{error}") from error


def check_for_update(build_info, *, opener=None):
    """Stable only; a newer release without a compatible manifest is not installed."""
    if build_info.channel != "stable":
        raise UpdateCheckError("当前自动更新仅支持 stable 通道。")
    release = read_json(RELEASE_API, opener=opener)
    if release.get("draft") or release.get("prerelease"):
        raise UpdateCheckError("stable 通道不会安装草稿或预发布版本。")
    tag = release.get("tag_name", "")
    latest = tag[1:] if isinstance(tag, str) and tag.startswith("v") else tag
    if version_key(latest) <= version_key(build_info.version):
        return None
    release_url = release.get("html_url", "")
    expected_release = f"https://github.com/{REPOSITORY}/releases/tag/{tag}"
    if release_url != expected_release:
        raise UpdateCheckError("发行版地址与项目不一致。")
    assets = release.get("assets")
    if not isinstance(assets, list):
        raise UpdateCheckError("发行版下载文件列表无效。")
    names = [a.get("name") for a in assets if isinstance(a, dict)]
    if (len(names) != len(assets) or any(not isinstance(name, str) or not name for name in names)
            or len(set(names)) != len(names)):
        raise UpdateCheckError("发行版包含重复或无效的下载文件。")
    metadata = next((a for a in assets if a["name"] == "update-manifest.json"), None)
    if metadata is None:
        raise UpdateCheckError("该版本没有兼容的更新清单，请从发布页手动下载。")
    expected_metadata = f"https://github.com/{REPOSITORY}/releases/download/{tag}/update-manifest.json"
    if metadata.get("browser_download_url") != expected_metadata:
        raise UpdateCheckError("更新清单地址与项目发行版不一致。")
    manifest = validate_release_manifest(read_json(expected_metadata, opener=opener), build_info)
    if manifest["version"] != latest:
        raise UpdateCheckError("发行版标签与更新清单版本不一致。")
    asset = dict(manifest["assets"][build_info.variant])
    published = next((a for a in assets if a["name"] == asset["file"]), None)
    if published is None:
        raise UpdateCheckError("发行版缺少当前发行类型的下载文件。")
    size = published.get("size")
    if type(size) is not int or not 0 < size <= 8 * 1024**3:
        raise UpdateCheckError("下载大小无效。")
    if "size" in asset and asset["size"] != size:
        raise UpdateCheckError("下载大小与更新清单不一致。")
    expected_url = f"https://github.com/{REPOSITORY}/releases/download/{tag}/{asset['file']}"
    if published.get("browser_download_url") != expected_url:
        raise UpdateCheckError("下载地址与已验证的发行版不一致。")
    asset.update(url=trusted_https(expected_url), size=size)
    notes = manifest.get("release_notes") or release.get("body") or "此版本未提供更新说明。"
    if not isinstance(notes, str):
        raise UpdateCheckError("更新说明格式无效。")
    return UpdateOffer(latest, manifest, asset, notes, release_url)

"""LDAP/LLDAP 认证模块"""

import threading
from settings_store import get_setting

_lock = threading.Lock()


def _get_ldap3():
    try:
        import ldap3
        return ldap3
    except ImportError:
        return None


def ldap_authenticate(username: str, password: str) -> dict:
    """LLDAP 验证：Bind DN 搜索用户 -> 查 admin 组 -> 用户密码 bind"""
    ldap3 = _get_ldap3()
    if ldap3 is None:
        raise RuntimeError("ldap3 未安装")

    url = get_setting("lldap_url", "")
    bind_dn = get_setting("lldap_bind_dn", "")
    bind_password = get_setting("lldap_bind_password", "")
    base_dn = get_setting("lldap_base_dn", "")
    admin_group = get_setting("lldap_admin_group", "admins") or "admins"

    if not url or not bind_dn or not base_dn:
        return None

    use_ssl = url.startswith("ldaps://")
    server = ldap3.Server(url, use_ssl=use_ssl)

    with _lock:
        try:
            conn = ldap3.Connection(server, user=bind_dn, password=bind_password,
                                    auto_bind=True, read_only=True)
        except Exception:
            return None

        try:
            conn.search(search_base=base_dn, search_filter="(uid={})".format(username),
                        attributes=["uid", "mail", "cn"])
            if not conn.entries:
                conn.unbind()
                return None

            entry = conn.entries[0]
            user_dn = entry.entry_dn
            email = str(entry.mail.value) if hasattr(entry, "mail") and entry.mail.value else ""

            is_admin = False
            try:
                group_base = base_dn.replace("ou=people", "ou=groups", 1)
                if group_base == base_dn:
                    group_base = "ou=groups," + base_dn.split(",", 1)[1] if "," in base_dn else base_dn
                conn.search(search_base=group_base,
                            search_filter="(cn={})".format(admin_group),
                            attributes=["uniqueMember"])
                if conn.entries:
                    members = conn.entries[0].uniqueMember.value if hasattr(conn.entries[0], "uniqueMember") else []
                    if isinstance(members, str):
                        members = [members]
                    for m in members or []:
                        if str(m).lower() == user_dn.lower():
                            is_admin = True
                            break
            except Exception:
                pass

            conn.unbind()
        except Exception:
            try:
                conn.unbind()
            except Exception:
                pass
            return None

    try:
        uc = ldap3.Connection(server, user=user_dn, password=password,
                              auto_bind=True, read_only=True)
        uc.unbind()
    except Exception:
        return None

    return {"username": username, "email": email, "is_admin": is_admin, "dn": user_dn}


def ldap_create_user(username: str, password: str, email: str = "") -> tuple:
    """
    在 LLDAP 中创建用户：
    1. ldapadd 建用户（不带密码）
    2. ldappasswd 设密码（LLDAP 不接受 LDAP 直写 userPassword）
    返回 (ok: bool, error_msg: str)
    """
    import subprocess

    url = get_setting("lldap_url", "")
    bind_dn = get_setting("lldap_bind_dn", "")
    bind_password = get_setting("lldap_bind_password", "")
    base_dn = get_setting("lldap_base_dn", "")

    if not url or not bind_dn or not base_dn:
        return False, "LDAP 未配置"

    host_part = url.replace("ldap://", "").replace("ldaps://", "")
    ldap_uri = "ldaps://" + host_part if url.startswith("ldaps") else "ldap://" + host_part

    user_dn = "uid={},{}".format(username, base_dn)
    from settings_store import get_setting
    _domain = (get_setting("platform_domain", "") or "").strip() or "localhost"
    mail = email or "{}@{}".format(username, _domain)

    ldif_lines = [
        "dn: " + user_dn,
        "objectClass: inetOrgPerson",
        "uid: " + username,
        "cn: " + username,
        "sn: " + username,
        "mail: " + mail,
    ]
    ldif = chr(10).join(ldif_lines) + chr(10)

    try:
        r1 = subprocess.run(
            ["ldapadd", "-x", "-H", ldap_uri, "-D", bind_dn, "-w", bind_password],
            input=ldif, capture_output=True, text=True, timeout=10
        )
        if r1.returncode != 0 and "Already exists" not in r1.stderr:
            return False, "LDAP 创建失败: " + (r1.stderr.strip()[:120] or "unknown")

        r2 = subprocess.run(
            ["ldappasswd", "-x", "-H", ldap_uri, "-D", bind_dn, "-w", bind_password,
             "-s", password, user_dn],
            capture_output=True, text=True, timeout=10
        )
        if r2.returncode != 0:
            return False, "LDAP 密码设置失败: " + (r2.stderr.strip()[:120] or "unknown")

        return True, ""
    except FileNotFoundError:
        return False, "服务器缺少 ldap-utils (ldapadd/ldappasswd)"
    except Exception as e:
        return False, "LDAP 异常: " + str(e)[:120]

# SPEC-006 — Ansible Playbook Structure

**Version:** 0.1  
**Status:** Draft  
**Depends on:** SPEC-003  

---

## 1. Overview

Ansible is the configuration management layer for Selene. It runs on
the EC2 instance itself (localhost execution — no control node needed).
Every time the EC2 starts, Ansible runs and applies the full desired
state from Git. This is what makes the EC2 stateless and recoverable.

**Core principle:** Nothing is configured on the server directly.
All changes go through Git, then Ansible. This applies to rules,
suppressions, ossec.conf, and service configuration.

---

## 2. Repository Layout

```
selene/
└── ansible/
    ├── site.yml                    # Master playbook — entry point
    ├── inventory/
    │   └── localhost               # Single host: the EC2 itself
    └── roles/
        ├── wazuh_config/           # Renders ossec.conf from template
        │   ├── tasks/
        │   │   └── main.yml
        │   └── templates/
        │       └── ossec.conf.j2
        ├── wazuh_rules/            # Deploys custom rules and suppressions
        │   └── tasks/
        │       └── main.yml
        ├── wazuh_indexer/          # Configures connection to OpenSearch
        │   └── tasks/
        │       └── main.yml
        └── wazuh_services/         # Starts/restarts Wazuh services
            └── tasks/
                └── main.yml

selene/
└── wazuh/
    ├── rules/
    │   └── local_rules.xml         # Custom detection rules
    ├── suppressions/
    │   └── local_overrides.xml     # Alert suppressions
    └── templates/
        └── ossec.conf.j2           # Jinja2 template for ossec.conf
```

---

## 3. Playbook Design

### 3.1 site.yml (master playbook)

Runs all roles in dependency order:

```yaml
- hosts: localhost
  connection: local
  become: yes
  vars:
    opensearch_endpoint: "{{ opensearch_endpoint }}"
    cloudtrail_bucket: "{{ cloudtrail_bucket }}"
  roles:
    - wazuh_config
    - wazuh_rules
    - wazuh_indexer
    - wazuh_services
```

Variables are passed in by UserData via `--extra-vars`.

### 3.2 Role: wazuh_config

Renders `ossec.conf.j2` using the passed variables and deploys it to
`/var/ossec/etc/ossec.conf`. Triggers a service restart if the file
changes (idempotent — no restart if unchanged).

Key template variables:
- `opensearch_endpoint` — OpenSearch VPC hostname
- `cloudtrail_bucket` — S3 bucket name for log polling

### 3.3 Role: wazuh_rules

Copies `wazuh/rules/local_rules.xml` to `/var/ossec/etc/rules/`.
Copies `wazuh/suppressions/local_overrides.xml` to `/var/ossec/etc/`.
Triggers service restart if either file changes.

### 3.4 Role: wazuh_indexer

Configures the Wazuh indexer to forward alerts to the external
OpenSearch domain rather than the local bundled indexer.
This is the key configuration that makes findings durable.

### 3.5 Role: wazuh_services

Ensures all Wazuh services are running:
- `wazuh-manager`
- `wazuh-indexer`
- `wazuh-dashboard`

Uses `systemd` module. Idempotent — only starts services that are
not already running.

---

## 4. Idempotency Requirement

Running `ansible-playbook site.yml` multiple times must produce
the same result and must not restart services unless configuration
has actually changed. This is enforced by using Ansible's `notify`
and `handler` pattern — handlers only fire when a task reports
`changed`.

---

## 5. Updating Configuration

### Adding or modifying a rule:
1. Edit `wazuh/rules/local_rules.xml`
2. Commit and push to `main`
3. SSH to EC2: `ansible-playbook /opt/selene/ansible/site.yml`
4. Ansible detects the file changed, copies it, restarts Wazuh

### Modifying ossec.conf:
1. Edit `wazuh/templates/ossec.conf.j2`
2. Commit and push to `main`
3. Re-run playbook — only the config role fires a restart

### Emergency rule change (incident response):
Even during an incident, changes go through Git. The playbook
re-run takes ~60 seconds. This is acceptable. Direct file edits
on the server are prohibited because they will be overwritten on
the next playbook run.

---

## 6. Acceptance Criteria

| ID | Criterion |
|---|---|
| AC1 | Running `site.yml` on a fresh AMI produces a fully working Wazuh instance |
| AC2 | Running `site.yml` again with no Git changes produces zero `changed` tasks |
| AC3 | Editing `local_rules.xml`, committing, and re-running activates the rule |
| AC4 | `ossec.conf` on the server matches the rendered template exactly |
| AC5 | No Wazuh config files exist that are not managed by Ansible |
| AC6 | Playbook completes in under 5 minutes on a fresh instance |

---
sidebarDepth: 2
editLink: false
---
# Tenant

!!! warning Experimental
    <div class="experimental-warning">
    <svg
        aria-hidden="true"
        focusable="false"
        role="img"
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 448 512"
        >
    <path
    fill="#e90"
    d="M437.2 403.5L320 215V64h8c13.3 0 24-10.7 24-24V24c0-13.3-10.7-24-24-24H120c-13.3 0-24 10.7-24 24v16c0 13.3 10.7 24 24 24h8v151L10.8 403.5C-18.5 450.6 15.3 512 70.9 512h306.2c55.7 0 89.4-61.5 60.1-108.5zM137.9 320l48.2-77.6c3.7-5.2 5.8-11.6 5.8-18.4V64h64v160c0 6.9 2.2 13.2 5.8 18.4l48.2 77.6h-172z"
    >
    </path>
    </svg>

    <div>
    The functionality here is experimental, and may change between versions without notice. Use at your own risk.
    </div>
    </div>


---

 ## TenantView
 <div class='class-sig' id='prefect-backend-tenant-tenantview'><p class="prefect-sig">class </p><p class="prefect-class">prefect.backend.tenant.TenantView</p>(tenant_id, name, slug)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/backend/tenant.py#L9">[source]</a></span></div>

A view of tenant data stored in the Prefect API.

This object is designed to be an immutable view of the data stored in the Prefect backend API at the time it is created

EXPERIMENTAL: This interface is experimental and subject to change

**Args**:     <ul class="args"><li class="args">`tenant_id`: The uuid of the tenant     </li><li class="args">`name`: The name of the tenant     </li><li class="args">`slug`: A machine compatible unique identifier for the tenant</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-backend-tenant-tenantview-from-current-tenant'><p class="prefect-class">prefect.backend.tenant.TenantView.from_current_tenant</p>()<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/backend/tenant.py#L132">[source]</a></span></div>
<p class="methods">Get an instance of this class filled with information by querying for the tenant id set in the Prefect Client<br><br>**Returns**:     A populated `TenantView` instance</p>|
 | <div class='method-sig' id='prefect-backend-tenant-tenantview-from-tenant-id'><p class="prefect-class">prefect.backend.tenant.TenantView.from_tenant_id</p>(tenant_id)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/backend/tenant.py#L116">[source]</a></span></div>
<p class="methods">Get an instance of this class filled with information by querying for the given tenant id<br><br>**Args**:     <ul class="args"><li class="args">`tenant_id`: the tenant to lookup</li></ul> **Returns**:     A populated `TenantView` instance</p>|

---
<br>


<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>on February 23, 2022 at 19:26 UTC</p>
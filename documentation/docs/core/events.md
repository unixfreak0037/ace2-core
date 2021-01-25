# Events

Every significant event that the core does can be subscribed to. Subscribers receive notifications when events are fired. Events are triggered by specific conditions.

## Available Events

<table>
<tr>
    <th><b>Event</b></th>
    <th><b>Args</b></th>
    <th><b>Description</b></th>
</tr>
<tr>
    <td colspan="3"><b>Root Analysis Events</b></td>
</tr>
<tr>
    <td><code>/core/analysis/root/new</code></td>
    <td><code>root</code></td>
    <td>A new root added.</td>
</tr>
<tr>
    <td><code>/core/analysis/root/modified</code></td>
    <td><code>root</code></td>
    <td>Root analysis updated.</td>
</tr>
<tr>
    <td><code>/core/analysis/root/deleted</code></td>
    <td><code>root_uuid</code></td>
    <td>Root analysis deleted.</td>
</tr>
<tr>
    <td colspan="3"><b>Analysis Detail Events</b></td>
</tr>
<tr>
    <td><code>/core/analysis/details/new</code></td>
    <td><code>root, uuid</code></td>
    <td>Analysis detail added.</td>
</tr>
<tr>
    <td><code>/core/analysis/details/modified</code></td>
    <td><code>root, uuid</code></td>
    <td>Analysis detail updated.</td>
</tr>
<tr>
    <td><code>/core/analysis/details/deleted</code></td>
    <td><code>uuid</code></td>
    <td>Analysis detail deleted.</td>
</tr>
</table>
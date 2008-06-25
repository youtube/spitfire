<table>
{foreach from=$tab item=row}
<tr>
{foreach from=$row item=ref}
<td>{$ref}</td>
{/foreach}
</tr>
{/foreach}
</table>

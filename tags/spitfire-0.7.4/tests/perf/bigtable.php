<?

$table = array_fill(0, 1000, array("a"=>1, "b"=>2, "c"=>3, "d"=>4, "e"=>5, "f"=>6, "g"=>7, "h"=>8, "i"=>9, "j"=>10));

function test_bigtable($table)
{
 ob_start();
?>
<table>
<?
foreach($table as $rowNum => $row)
{
?>
  <tr>
<?
  foreach($row as $value)
  {
?>
   <td><? echo $value; ?></td>
<?
  }
?>
  </tr>
<?
}
?>
</table>
<?
 return ob_get_clean();
}

require "Smarty-2.6.18/libs/Smarty.class.php";

$smarty = new Smarty();
$smarty->compile_dir = ".";
$smarty->template_dir = ".";
$smarty->assign("tab", $table);
$smarty->fetch("bigtable.tpl");

$request_count = 10;

$start = microtime(true);
for ($i = 0; $i < $request_count; $i++)
{
  $smarty->assign("tab", $table);
  $smarty->fetch("bigtable.tpl");
}
$elapsed = microtime(true) - $start;
$time_per_request = ($elapsed / $request_count) * 1000;
echo "Smarty: $time_per_request ms\n";

$start = microtime(true);
for ($i = 0; $i < $request_count; $i++)
{
  test_bigtable($table);
}
$elapsed = microtime(true) - $start;
$time_per_request = ($elapsed / $request_count) * 1000;
echo "PHP: $time_per_request ms\n";
?>

---
sidebarDepth: 2
editLink: false
---
# File and Filesystem Tasks
---
Tasks for working with files and filesystems.
 ## Copy
 <div class='class-sig' id='prefect-tasks-files-operations-copy'><p class="prefect-sig">class </p><p class="prefect-class">prefect.tasks.files.operations.Copy</p>(source_path=&quot;&quot;, target_path=&quot;&quot;, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/files/operations.py#L69">[source]</a></span></div>

Task for copying files or directories within the file system.

**Args**:     <ul class="args"><li class="args">`source_path (Union[str, Path], optional)`: the path to the source directory/file.     </li><li class="args">`target_path (Union[str, Path], optional)`: the path to the target directory/file.         If copying a directory: the `target_path` must not exists.     </li><li class="args">`**kwargs (dict, optional)`: additional keyword arguments to pass to the         Task constructor</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-tasks-files-operations-copy-run'><p class="prefect-class">prefect.tasks.files.operations.Copy.run</p>(source_path=&quot;&quot;, target_path=&quot;&quot;)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/files/operations.py#L91">[source]</a></span></div>
<p class="methods">Task run method.<br><br>**Args**:     <ul class="args"><li class="args">`source_path (Union[str, Path], optional)`: the path to the source directory/file.     </li><li class="args">`target_path (Union[str, Path], optional)`: the path to the target directory/file.         If copying a directory: the `target_path` must not exists.</li></ul> **Returns**:     <ul class="args"><li class="args">`Path`: resulting path of the copied file / directory</li></ul></p>|

---
<br>

 ## Move
 <div class='class-sig' id='prefect-tasks-files-operations-move'><p class="prefect-sig">class </p><p class="prefect-class">prefect.tasks.files.operations.Move</p>(source_path=&quot;&quot;, target_path=&quot;&quot;, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/files/operations.py#L9">[source]</a></span></div>

Task for moving files or directories within the file system.

**Args**:     <ul class="args"><li class="args">`source_path (Union[str, Path], optional)`: the path to the source directory/file.     </li><li class="args">`target_path (Union[str, Path], optional)`: the path to the target directory/file. Any         parent directories of `target_path` must already exist.     </li><li class="args">`**kwargs (dict, optional)`: additional keyword arguments to pass to the         Task constructor</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-tasks-files-operations-move-run'><p class="prefect-class">prefect.tasks.files.operations.Move.run</p>(source_path=&quot;&quot;, target_path=&quot;&quot;)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/files/operations.py#L31">[source]</a></span></div>
<p class="methods">Task run method.<br><br>**Args**:     <ul class="args"><li class="args">`source_path (Union[str, Path], optional)`: the path to the source directory/file.     </li><li class="args">`target_path (Union[str, Path], optional)`: the path to the target directory/file. Any         parent directories of `target_path` must already exist.</li></ul> **Returns**:     <ul class="args"><li class="args">`Path`: resulting path of the moved file / directory</li></ul></p>|

---
<br>

 ## Remove
 <div class='class-sig' id='prefect-tasks-files-operations-remove'><p class="prefect-sig">class </p><p class="prefect-class">prefect.tasks.files.operations.Remove</p>(path=&quot;&quot;, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/files/operations.py#L131">[source]</a></span></div>

Task for removing files or directories within the file system.

**Args**:     <ul class="args"><li class="args">`path (Union[str, Path], optional)`: file or directory to be removed         If deleting a directory, the directory must be empty.     </li><li class="args">`**kwargs (dict, optional)`: additional keyword arguments to pass to the         Task constructor</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-tasks-files-operations-remove-run'><p class="prefect-class">prefect.tasks.files.operations.Remove.run</p>(path=&quot;&quot;)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/files/operations.py#L150">[source]</a></span></div>
<p class="methods">Task run method.<br><br>**Args**:     <ul class="args"><li class="args">`path (Union[str, Path], optional)`: file or directory to be removed</li></ul></p>|

---
<br>

 ## Unzip
 <div class='class-sig' id='prefect-tasks-files-compression-unzip'><p class="prefect-sig">class </p><p class="prefect-class">prefect.tasks.files.compression.Unzip</p>(zip_path=&quot;&quot;, extract_dir=&quot;&quot;, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/files/compression.py#L16">[source]</a></span></div>

Task for unzipping data.

**Args**:     <ul class="args"><li class="args">`zip_path (Union[str, Path], optional)`: the path to the zip file     </li><li class="args">`extract_dir (Union[str, Path], optional)`: directory to extract the zip file into.         If not provided, the current working directory will be used. This directory must         already exist.     </li><li class="args">`**kwargs (dict, optional)`: additional keyword arguments to pass to the         Task constructor</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-tasks-files-compression-unzip-run'><p class="prefect-class">prefect.tasks.files.compression.Unzip.run</p>(zip_path=&quot;&quot;, extract_dir=&quot;&quot;, password=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/files/compression.py#L39">[source]</a></span></div>
<p class="methods">Task run method.<br><br>**Args**:     <ul class="args"><li class="args">`zip_path (Union[str, Path], optional)`: the path to the zip file     </li><li class="args">`extract_dir (Union[str, Path], optional)`: directory to extract the zip file into.         If not provided, the current working directory will be used. This directory must         already exist.     </li><li class="args">`password (Union[bytes, str], optional)`: password for unzipping a password-protected         zip file. If a `str`, will be utf-8 encoded.</li></ul> **Returns**:     <ul class="args"><li class="args">`Path`: path to the extracted directory.</li></ul></p>|

---
<br>

 ## Zip
 <div class='class-sig' id='prefect-tasks-files-compression-zip'><p class="prefect-sig">class </p><p class="prefect-class">prefect.tasks.files.compression.Zip</p>(source_path=&quot;&quot;, zip_path=&quot;&quot;, compression_method=&quot;deflate&quot;, compression_level=None, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/files/compression.py#L85">[source]</a></span></div>

Task to create a zip archive.

**Args**:     <ul class="args"><li class="args">`source_path (Union[str, Path, List[str], List[Path]], optional)`: path or paths to compress          into a single zip archive.     </li><li class="args">`zip_path (Union[str, Path], optional)`: path to the output archive file. Any parent         directories of `zip_path` must already exist.     </li><li class="args">`compression_method (str, optional)`: the compression method to use. Options are         "deflate", "store", "bzip2", and "lzma". Defaults to `"deflate"`.     </li><li class="args">`compression_level (int, optional)`: Compression level to use,         see https://docs.python.org/3/library/zipfile.html#zipfile.ZipFile for more info.         Python 3.7+ only.     </li><li class="args">`**kwargs (dict, optional)`: additional keyword arguments to pass to the         Task constructor.</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-tasks-files-compression-zip-run'><p class="prefect-class">prefect.tasks.files.compression.Zip.run</p>(source_path=&quot;&quot;, zip_path=&quot;&quot;)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/files/compression.py#L130">[source]</a></span></div>
<p class="methods">Task run method.<br><br>**Args**:     <ul class="args"><li class="args">`source_path (Union[str, Path, List[str], List[Path]], optional)`: path or paths to compress         into a single zip archive.     </li><li class="args">`zip_path (Union[str, Path], optional)`: path to the output archive file. Any parent         directories of `zip_path` must already exist.</li></ul></p>|

---
<br>


<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>on July 1, 2021 at 18:35 UTC</p>
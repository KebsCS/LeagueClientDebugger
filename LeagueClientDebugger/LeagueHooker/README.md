# LeagueHooker
Disables SSL verifications by hooking OpenSSL functions and attaches a debug console with logs by opening output streams and compiling with the /MD flag


## Finding function signatures
1. Find x64 process that has libssl loaded. This can be done with Process Hacker -> Find Handles or DLLs
2. In my case, it is `C:\Program Files\NVIDIA Corporation\NvContainer\libssl-1_1.dll`. Open it in IDA or Ghidra
3. For `X509_verify_cert` function open `libcrypto-1_1.dll` instead
4. In Exports, look for the function that you're updating the offset for and jump to its definition
5. If the function has only a call to `function_name_0`, jump inside it
6. Make a signature using Hex View by copying the hex code and replacing bytes that could be dynamic with `??`
#include "pch.h"


//using ssl_verify_cert_chain_type = int(*)(void* ssl, void* param2);
//ssl_verify_cert_chain_type ssl_verify_cert_chain_original = nullptr;

using SSL_CTX_set_verify_type = int(*)(void* ssl_ctx, int mode, void* callback);
SSL_CTX_set_verify_type SSL_CTX_set_verify_original = nullptr;

using X509_verify_cert_type = int(*)(void* ctx);
X509_verify_cert_type X509_verify_cert_original = nullptr;

using SSL_get_verify_result_type = long(__fastcall*)(const void* ssl);
SSL_get_verify_result_type SSL_get_verify_result_original = nullptr;

int SSL_CTX_set_verify_hook(void* ssl_ctx, int mode, void* callback)
{
	return SSL_CTX_set_verify_original(ssl_ctx, 0, callback);
}

int X509_verify_cert_hook(void* ctx)
{
	return 1;
}

int SSL_get_verify_result_hook(const void* ssl)
{
	return 0; //X509_V_OK
}

__declspec(safebuffers)void WINAPI InitThread(HMODULE hModule) noexcept
{
	HANDLE modBase = GetModuleHandle(NULL);

	AllocConsole();
	FILE* f;
	freopen_s(&f, "CONOUT$", "w", stdout);
	freopen_s(&f, "CONOUT$", "w", stderr);
	freopen_s(&f, "CONIN$", "r", stdin);
	std::cout.clear();
	std::clog.clear();
	std::cerr.clear();
	std::cin.clear();

	// std::wcout, std::wclog, std::wcerr, std::wcin
	HANDLE hConOut = CreateFile(TEXT("CONOUT$"), GENERIC_READ | GENERIC_WRITE, FILE_SHARE_READ | FILE_SHARE_WRITE, NULL, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
	HANDLE hConIn = CreateFile(TEXT("CONIN$"), GENERIC_READ | GENERIC_WRITE, FILE_SHARE_READ | FILE_SHARE_WRITE, NULL, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
	SetStdHandle(STD_OUTPUT_HANDLE, hConOut);
	SetStdHandle(STD_ERROR_HANDLE, hConOut);
	SetStdHandle(STD_INPUT_HANDLE, hConIn);
	std::wcout.clear();
	std::wclog.clear();
	std::wcerr.clear();
	std::wcin.clear();

	MH_Initialize();

	uintptr_t SSL_CTX_set_verify_addr = FindPattern(modBase, "89 91 58 01 00 00 4C 89 81 88 01 00 00") + 0x0;
	if (!SSL_CTX_set_verify_addr)
	{
		printf("SSL_CTX_set_verify_addr not found");
	}
	MH_CreateHook((LPVOID)SSL_CTX_set_verify_addr, SSL_CTX_set_verify_hook, reinterpret_cast<void**>(&SSL_CTX_set_verify_original));

	uintptr_t X509_verify_cert_addr = FindPattern(modBase, "48 89 5C 24 08 57 B8 30 00 00 00 E8 ?? ?? ?? ?? 48 2B E0 48 8B B9 E8 00 00 00") + 0x0;
	if (!X509_verify_cert_addr)
	{
		printf("X509_verify_cert_addr not found");
	}
	MH_CreateHook((LPVOID)X509_verify_cert_addr, X509_verify_cert_hook, reinterpret_cast<void**>(&X509_verify_cert_original));

	uintptr_t SSL_get_verify_result_addr = FindPattern(modBase, "8B 81 A8 05 00 00") + 0x0;
	if (!SSL_get_verify_result_addr)
	{
		printf("SSL_get_verify_result_addr not found");
	}
	MH_CreateHook((LPVOID)SSL_get_verify_result_addr, SSL_get_verify_result_hook, reinterpret_cast<void**>(&SSL_get_verify_result_original));

	MH_EnableHook(MH_ALL_HOOKS);

	while (!(GetAsyncKeyState(VK_END) & 0x8000))
	{
		std::this_thread::sleep_for(std::chrono::milliseconds(1));
	}

	MH_DisableHook(MH_ALL_HOOKS);

	MH_Uninitialize();

	fclose(f);
	CloseHandle(hConOut);
	CloseHandle(hConIn);
	FreeConsole();
	FreeLibraryAndExitThread(static_cast<HMODULE>(hModule), ERROR_SUCCESS);
}

BOOL APIENTRY DllMain(HMODULE hModule,
	DWORD  ul_reason_for_call,
	LPVOID lpReserved
)
{
	DisableThreadLibraryCalls(hModule);

	switch (ul_reason_for_call)
	{
	case DLL_PROCESS_ATTACH:
		CloseHandle((HANDLE)_beginthreadex(nullptr, 0, reinterpret_cast<_beginthreadex_proc_type>(InitThread), hModule, 0, nullptr));
		break;
	case DLL_THREAD_ATTACH:
		break;
	case DLL_THREAD_DETACH:
		break;
	case DLL_PROCESS_DETACH:
		break;
	}
	return TRUE;
}
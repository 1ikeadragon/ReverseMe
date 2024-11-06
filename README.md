>As Jordan mentioned in [issue #1](https://github.com/1ikeadragon/ReverseMe/issues/1#issue-2638229516) , dogbolt shouldn't be automated as it puts them in the risk of losing the commercial licenses. As a result, **only the decompilation features** of the bot have been **turned off temporarily** until I get the time to spin up a self-hosted light-weight fork of dogbolt with the open-source and enterprise decompilers given that we have a subscription to them. Till then you can use disassembly and hexdump.

# ReverseMe
Simple reverse engineering discord bot that queries dogbolt for decompilation. Add it: [ReverseMe Bot](https://discord.com/oauth2/authorize?client_id=1302859968147619880)

### Usage
Decompile with IDA, Ghidra, Binja, Angr:
```
;revme 
```
Decompile with IDA/Binja/Ghidra/Angr:
```
;revme binja/ida/ghidra/angr
```
Get the hexdump:
```
;revme hex
```
Get the disassembly(intel):
```
;revme asm
```

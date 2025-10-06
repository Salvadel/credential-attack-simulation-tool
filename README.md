<h1>Credential Attack Simulation Tool</h1>

<h2>Description</h2>
This project consists of a C program that attempts to crack up to 100 user-provided passwords (max 20 chars) using two methods. First, it checks each password against a leaked wordlist (rockyou.txt). If not found, a brute-force engine generates combinations (limited to 8 chars) from letters, numbers, and symbols. It reports total attempts and elapsed time (shows "instantly" if <0.01s) and offers to run again.
<br> </br>
Note that the program must be downloaded using Git Large File Storage (LFS). Alternatively, you can download it from the GitHub web app and replace the 'src/directories/rockyou.txt' file with a locally downloaded version (https://weakpass.com/wordlists/rockyou.txt).
<br />

<h2>Languages and Utilities Used</h2>

- <b>C</b>
- <b>rockyou.txt (password list)</b> 

<h2>Environments Used </h2>

- <b>Windows 11</b> (21H2)

<h2>Program walk-through:</h2>

<p align="center">
Launch the utility.exe, enter how many passwords to crack: <br/>
<img src="https://i.imgur.com/WWoWpL8.jpeg" height="80%" width="80%" alt="Disk Sanitization Steps"/>
<br />
<br />
Enter the passwords you want to test:  <br/>
<img src="https://i.imgur.com/Wh1LTc6.jpeg" height="80%" width="80%" alt="Disk Sanitization Steps"/>
<br />
<br />
View results:  <br/>
<img src="https://i.imgur.com/uIfYqxV.jpeg" height="80%" width="80%" alt="Disk Sanitization Steps"/>
<br />
<br />
Indication if you would like to restart the program:  <br/>
<img src="https://i.imgur.com/tFm73MM.jpeg" height="80%" width="80%" alt="Disk Sanitization Steps"/>
<br />
<br />


<!--
 ```diff
- text in red
+ text in green
! text in orange
# text in gray
@@ text in purple (and bold)@@
```
--!>


// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

import "forge-std/Test.sol";
import "../src/HYQUBWallet.sol";
import "../src/HYQUBRegistry.sol";

contract HYQUBWalletTest is Test {
    HYQUBWallet wallet;
    HYQUBRegistry registry;

    address deployer = address(this);
    address attacker = address(0xBEEF);
    address approvalSigner =
        address(0x1111111111111111111111111111111111111111);
    address entryPoint =
        address(0xE4700000000000000000000000000000000E4700);

    function setUp() public {
        registry = new HYQUBRegistry();

        wallet = new HYQUBWallet(
            address(registry),
            approvalSigner,
            entryPoint
        );
    }

    // ------------------------------------------------------------------
    // Constructor
    // ------------------------------------------------------------------

    function test_OwnerIsDeployer() public view {
        assertEq(wallet.owner(), deployer);
    }

    function test_InitialNonceIsZero() public view {
        assertEq(wallet.nonce(), 0);
    }

    function test_RegistryIsConfigured() public view {
        assertEq(
            address(wallet.registry()),
            address(registry)
        );
    }

    function test_ApprovalSignerIsConfigured() public view {
        assertEq(
            wallet.approvalSigner(),
            approvalSigner
        );
    }

    function test_ConstructorRejectsZeroRegistry() public {
        vm.expectRevert(
            "HYQUBWallet: registry cannot be zero"
        );

        new HYQUBWallet(
            address(0),
            approvalSigner,
            entryPoint
        );
    }

    function test_ConstructorRejectsZeroApprovalSigner() public {
        vm.expectRevert(
            "HYQUBWallet: approval signer cannot be zero"
        );

        new HYQUBWallet(
            address(registry),
            address(0),
            entryPoint
        );
    }

    // ------------------------------------------------------------------
    // Deposit
    // ------------------------------------------------------------------

    function test_DepositIncreasesBalance() public {
        wallet.deposit{value: 1 ether}();

        assertEq(
            wallet.getBalance(),
            1 ether
        );
    }

    function test_ReceiveAcceptsPlainTransfer() public {
        (bool success, ) = address(wallet).call{
            value: 1 ether
        }("");

        assertTrue(success);

        assertEq(
            wallet.getBalance(),
            1 ether
        );
    }

    function test_RevertWhen_DepositIsZero() public {
        vm.expectRevert(
            "HYQUBWallet: deposit must be > 0"
        );

        wallet.deposit{value: 0}();
    }

    // ------------------------------------------------------------------
    // Withdraw
    // ------------------------------------------------------------------

    function test_OwnerCanWithdraw() public {
        wallet.deposit{value: 1 ether}();

        uint256 balanceBefore = attacker.balance;

        wallet.withdraw(
            payable(attacker),
            0.5 ether
        );

        assertEq(
            attacker.balance,
            balanceBefore + 0.5 ether
        );

        assertEq(
            wallet.getBalance(),
            0.5 ether
        );

        assertEq(
            wallet.nonce(),
            1
        );
    }

    function test_RevertWhen_NonOwnerWithdraws() public {
        wallet.deposit{value: 1 ether}();

        vm.prank(attacker);

        vm.expectRevert(
            "HYQUBWallet: caller is not the owner"
        );

        wallet.withdraw(
            payable(attacker),
            0.5 ether
        );
    }

    function test_RevertWhen_WithdrawExceedsBalance() public {
        vm.expectRevert(
            "HYQUBWallet: insufficient balance"
        );

        wallet.withdraw(
            payable(attacker),
            1 ether
        );
    }

    // ------------------------------------------------------------------
    // Execute
    // ------------------------------------------------------------------

    function test_OwnerCanExecuteCall() public {
        wallet.deposit{value: 1 ether}();

        wallet.execute(
            attacker,
            0.2 ether,
            ""
        );

        assertEq(
            attacker.balance,
            0.2 ether
        );

        assertEq(
            wallet.nonce(),
            1
        );
    }

    function test_RevertWhen_NonOwnerExecutes() public {
        vm.prank(attacker);

        vm.expectRevert(
            "HYQUBWallet: caller is not the owner or EntryPoint"
        );

        wallet.execute(
            attacker,
            0,
            ""
        );
    }
}

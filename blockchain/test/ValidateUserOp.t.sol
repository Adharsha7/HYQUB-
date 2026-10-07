// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

import "forge-std/Test.sol";
import "../src/HYQUBWallet.sol";
import "../src/HYQUBRegistry.sol";
import {PackedUserOperation} from "account-abstraction/interfaces/PackedUserOperation.sol";

contract ValidateUserOpTest is Test {
    HYQUBWallet wallet;
    HYQUBRegistry registry;

    address approvalSigner =
        address(0x1111111111111111111111111111111111111111);
    address entryPoint =
        address(0xE4700000000000000000000000000000000E4700);
    address attacker = address(0xBEEF);

    function setUp() public {
        registry = new HYQUBRegistry();
        wallet = new HYQUBWallet(
            address(registry),
            approvalSigner,
            entryPoint
        );
    }

    function _dummyUserOp() internal view returns (PackedUserOperation memory) {
        return PackedUserOperation({
            sender: address(wallet),
            nonce: 0,
            initCode: "",
            callData: "",
            accountGasLimits: bytes32(0),
            preVerificationGas: 0,
            gasFees: bytes32(0),
            paymasterAndData: "",
            signature: _wellFormedButRejectedSignature()
        });
    }

    /// @dev A syntactically valid (approvalPayload, approvalSignature) ABI
    ///      encoding that decodes cleanly at both levels but is rejected by
    ///      _validateHyqubApproval on the very first semantic check
    ///      (approvedWallet mismatch) — so it never touches the registry or
    ///      ecrecover, exercising the "well-formed but invalid" path.
    function _wellFormedButRejectedSignature() internal view returns (bytes memory) {
        bytes memory approvalPayload = abi.encode(
            "HYQUB_APPROVAL_V1",
            address(0x9999999999999999999999999999999999999999), // wrong wallet on purpose
            bytes32(0),
            uint256(1),
            uint256(1),
            uint256(1),
            new string[](0)
        );

        bytes memory approvalSignature = new bytes(65);

        return abi.encode(approvalPayload, approvalSignature);
    }

    function test_RevertWhen_NonEntryPointCallsValidateUserOp() public {
        PackedUserOperation memory userOp = _dummyUserOp();

        vm.prank(attacker);
        vm.expectRevert("HYQUBWallet: caller is not the EntryPoint");
        wallet.validateUserOp(userOp, bytes32(0), 0);
    }

    function test_EntryPointCanCallValidateUserOp() public {
        PackedUserOperation memory userOp = _dummyUserOp();

        vm.prank(entryPoint);
        uint256 validationData = wallet.validateUserOp(userOp, bytes32(0), 0);

        // Stub still returns fail-closed until Step 4 wires in
        // real HYQUB approval verification.
        assertEq(validationData, 1);
    }

    function test_RevertWhen_SignatureIsMalformed() public {
        PackedUserOperation memory userOp = _dummyUserOp();
        userOp.signature = abi.encode(bytes("deadbeef"), bytes("deadbeef"));

        vm.prank(entryPoint);
        vm.expectRevert();
        wallet.validateUserOp(userOp, bytes32(0), 0);
    }

    function test_EntryPointCallWithMissingFundsPaysPrefund() public {
        vm.deal(address(wallet), 1 ether);

        uint256 entryPointBalanceBefore = entryPoint.balance;

        PackedUserOperation memory userOp = _dummyUserOp();

        vm.prank(entryPoint);
        wallet.validateUserOp(userOp, bytes32(0), 0.1 ether);

        assertEq(entryPoint.balance, entryPointBalanceBefore + 0.1 ether);
    }
}

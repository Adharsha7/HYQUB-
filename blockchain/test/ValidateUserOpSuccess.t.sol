// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

import "forge-std/Test.sol";
import "../src/HYQUBWallet.sol";
import "../src/HYQUBRegistry.sol";
import {PackedUserOperation} from "account-abstraction/interfaces/PackedUserOperation.sol";

contract ValidateUserOpSuccessTest is Test {
    HYQUBWallet wallet;
    HYQUBRegistry registry;

    uint256 signerPrivateKey = 0xA11CE;
    address approvalSigner;

    address entryPoint =
        address(0xE4700000000000000000000000000000000E4700);

    function setUp() public {
        approvalSigner = vm.addr(signerPrivateKey);

        registry = new HYQUBRegistry();
        wallet = new HYQUBWallet(
            address(registry),
            approvalSigner,
            entryPoint
        );

        registry.registerWallet(address(wallet), bytes32(uint256(1)));
        // keyVersion is now 2 after one rotation, matching the pattern
        // used in TransactionIntentReconstruction.t.sol.
        registry.rotateKey(address(wallet), bytes32(uint256(2)));
    }

    function _sign(bytes32 payloadHash) internal view returns (bytes memory) {
        bytes32 ethSignedMessageHash = keccak256(
            abi.encodePacked("\x19Ethereum Signed Message:\n32", payloadHash)
        );
        (uint8 v, bytes32 r, bytes32 s) = vm.sign(signerPrivateKey, ethSignedMessageHash);
        return abi.encodePacked(r, s, v);
    }

    function _buildValidUserOp(
        address target,
        uint256 value,
        bytes memory data,
        uint256 approvalNonce
    ) internal view returns (PackedUserOperation memory) {
        bytes memory callData = abi.encodeWithSelector(
            HYQUBWallet.execute.selector,
            target,
            value,
            data
        );

        uint256 keyVersion = registry.getKeyVersion(address(wallet));

        bytes memory transactionIntent = abi.encode(
            "HYQUB_TX_V1",
            block.chainid,
            address(wallet),
            target,
            value,
            data,
            keyVersion
        );
        bytes32 messageHash = sha256(transactionIntent);

        bytes memory approvalPayload = abi.encode(
            "HYQUB_APPROVAL_V1",
            address(wallet),
            messageHash,
            keyVersion,
            approvalNonce,
            block.timestamp,
            new string[](0)
        );

        bytes32 approvalHash = sha256(approvalPayload);
        bytes memory approvalSignature = _sign(approvalHash);

        bytes memory signature = abi.encode(approvalPayload, approvalSignature);

        return PackedUserOperation({
            sender: address(wallet),
            nonce: 0,
            initCode: "",
            callData: callData,
            accountGasLimits: bytes32(0),
            preVerificationGas: 0,
            gasFees: bytes32(0),
            paymasterAndData: "",
            signature: signature
        });
    }

    function test_ValidApprovalSucceeds() public {
        PackedUserOperation memory userOp = _buildValidUserOp(
            address(0x4444444444444444444444444444444444444444),
            0.01 ether,
            "",
            1
        );

        vm.prank(entryPoint);
        uint256 validationData = wallet.validateUserOp(userOp, bytes32(0), 0);

        assertEq(validationData, 0);
    }

    function test_ApprovalNonceCannotBeReplayed() public {
        PackedUserOperation memory userOp = _buildValidUserOp(
            address(0x4444444444444444444444444444444444444444),
            0.01 ether,
            "",
            7
        );

        vm.prank(entryPoint);
        uint256 firstResult = wallet.validateUserOp(userOp, bytes32(0), 0);
        assertEq(firstResult, 0);

        vm.prank(entryPoint);
        uint256 secondResult = wallet.validateUserOp(userOp, bytes32(0), 0);
        assertEq(secondResult, 1);
    }

    function test_TamperedTargetAfterApprovalFails() public {
        PackedUserOperation memory userOp = _buildValidUserOp(
            address(0x4444444444444444444444444444444444444444),
            0.01 ether,
            "",
            2
        );

        // Attacker swaps the target after the approval was signed,
        // without changing the signature.
        userOp.callData = abi.encodeWithSelector(
            HYQUBWallet.execute.selector,
            address(0x5555555555555555555555555555555555555555),
            0.01 ether,
            bytes("")
        );

        vm.prank(entryPoint);
        uint256 validationData = wallet.validateUserOp(userOp, bytes32(0), 0);

        assertEq(validationData, 1);
    }

    function test_WrongSignerFails() public {
        uint256 wrongPrivateKey = 0xBAD;
        PackedUserOperation memory userOp = _buildValidUserOp(
            address(0x4444444444444444444444444444444444444444),
            0.01 ether,
            "",
            3
        );

        // Re-sign the same payload with the wrong key.
        (bytes memory approvalPayload, ) = abi.decode(userOp.signature, (bytes, bytes));
        bytes32 approvalHash = sha256(approvalPayload);
        bytes32 ethSignedMessageHash = keccak256(
            abi.encodePacked("\x19Ethereum Signed Message:\n32", approvalHash)
        );
        (uint8 v, bytes32 r, bytes32 s) = vm.sign(wrongPrivateKey, ethSignedMessageHash);
        bytes memory badSignature = abi.encodePacked(r, s, v);

        userOp.signature = abi.encode(approvalPayload, badSignature);

        vm.prank(entryPoint);
        uint256 validationData = wallet.validateUserOp(userOp, bytes32(0), 0);

        assertEq(validationData, 1);
    }
}
